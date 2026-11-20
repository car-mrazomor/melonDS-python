// C API over the melonDS core (see melonds_shim.h).
#include "melonds_shim.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "NDS.h"
#include "NDSCart.h"
#include "Args.h"
#include "Savestate.h"
#include "SPI_Firmware.h"
#include "Platform.h"

#if defined(__APPLE__) && defined(__aarch64__)
#include <pthread.h>
#endif

using namespace melonDS;

// Apple Silicon: JIT memory is either writable or executable, per thread.
// melonDS's ~ARMJIT() switches the thread to "writable" and never back, so after
// destroying one JIT instance, another instance on the same thread would crash.
// Put the calling thread back in "executable" mode before running emulated code.
static inline void jit_thread_exec_mode()
{
#if defined(__APPLE__) && defined(__aarch64__)
    if (__builtin_available(macOS 11.0, *))
        pthread_jit_write_protect_np(1);
#endif
}

struct mds_t
{
    std::unique_ptr<NDS> nds;
    std::string rom_path;
    uint32_t keys = 0;       // pressed mask, 1 = pressed
    uint64_t frames = 0;
    bool rom_loaded = false;
};

static thread_local std::string g_last_error;

static int fail(const std::string& msg)
{
    g_last_error = msg;
    return -1;
}

// ---- file helpers --------------------------------------------------------

static bool read_file(const char* path, std::vector<u8>& out)
{
    FILE* f = std::fopen(path, "rb");
    if (!f) return false;
    std::fseek(f, 0, SEEK_END);
    long len = std::ftell(f);
    std::fseek(f, 0, SEEK_SET);
    if (len < 0) { std::fclose(f); return false; }
    out.resize((size_t)len);
    size_t got = len ? std::fread(out.data(), 1, (size_t)len, f) : 0;
    std::fclose(f);
    return got == (size_t)len;
}

template <size_t N>
static bool load_bios(const char* path, std::unique_ptr<std::array<u8, N>>& dst, const char* what)
{
    std::vector<u8> data;
    if (!read_file(path, data)) { g_last_error = std::string("cannot read ") + what + ": " + path; return false; }
    if (data.size() != N)
    {
        g_last_error = std::string(what) + " has wrong size (" + std::to_string(data.size()) +
                       ", expected " + std::to_string(N) + ")";
        return false;
    }
    dst = std::make_unique<std::array<u8, N>>();
    std::memcpy(dst->data(), data.data(), N);
    return true;
}

// ---- API -----------------------------------------------------------------

extern "C" {

const char* mds_last_error(void) { return g_last_error.c_str(); }

mds_t* mds_create(const char* bios9, const char* bios7, const char* firmware, int use_jit)
{
    g_last_error.clear();
    auto m = std::make_unique<mds_t>();

    NDSArgs args;
    if (bios9 && !load_bios<ARM9BIOSSize>(bios9, args.ARM9BIOS, "ARM9 BIOS")) return nullptr;
    if (bios7 && !load_bios<ARM7BIOSSize>(bios7, args.ARM7BIOS, "ARM7 BIOS")) return nullptr;

    if (firmware)
    {
        std::vector<u8> fw;
        if (!read_file(firmware, fw)) { g_last_error = std::string("cannot read firmware: ") + firmware; return nullptr; }
        args.Firmware = Firmware(fw.data(), (u32)fw.size());
        if (!args.Firmware.Buffer()) { g_last_error = "invalid firmware image"; return nullptr; }
    }
    else
    {
        args.Firmware = Firmware(0);
    }

#ifdef JIT_ENABLED
    if (!use_jit) args.JIT = std::nullopt;
#else
    args.JIT = std::nullopt;
    (void)use_jit;
#endif

    m->nds = std::make_unique<NDS>(std::move(args), m.get());
    m->nds->Reset();
    return m.release();
}

void mds_destroy(mds_t* m)
{
    delete m;
    jit_thread_exec_mode();
}

static void boot(mds_t* m)
{
    m->nds->Reset();
    if (m->nds->NeedsDirectBoot())
        m->nds->SetupDirectBoot(m->rom_path);
    m->nds->Start();
    m->nds->SetKeyMask(~m->keys & 0xFFF);
    m->frames = 0;
}

static int load_rom_data(mds_t* m, const u8* rom, u32 rom_len, const char* rom_name, const char* sav_path)
{
    NDSCart::NDSCartArgs cartargs {};
    if (sav_path)
    {
        std::vector<u8> sav;
        if (read_file(sav_path, sav) && !sav.empty())
        {
            cartargs.SRAM = std::make_unique<u8[]>(sav.size());
            std::memcpy(cartargs.SRAM.get(), sav.data(), sav.size());
            cartargs.SRAMLength = (u32)sav.size();
        }
    }

    auto romdata = std::make_unique<u8[]>(rom_len);
    std::memcpy(romdata.get(), rom, rom_len);
    auto cart = NDSCart::ParseROM(std::move(romdata), rom_len, m, std::move(cartargs));
    if (!cart) return fail("failed to parse ROM");

    m->rom_path = rom_name;
    m->nds->SetNDSCart(std::move(cart));
    m->rom_loaded = true;
    boot(m);
    return 0;
}

int mds_load_rom(mds_t* m, const char* rom_path, const char* sav_path)
{
    g_last_error.clear();
    if (!m || !rom_path) return fail("null argument");
    std::vector<u8> rom;
    if (!read_file(rom_path, rom)) return fail(std::string("cannot read ROM: ") + rom_path);
    return load_rom_data(m, rom.data(), (u32)rom.size(), rom_path, sav_path);
}

int mds_load_rom_mem(mds_t* m, const uint8_t* data, uint32_t len, const char* sav_path)
{
    g_last_error.clear();
    if (!m || !data || len == 0) return fail("empty ROM data");
    return load_rom_data(m, data, len, "rom.nds", sav_path);
}

int mds_write_save(mds_t* m, const char* sav_path)
{
    g_last_error.clear();
    if (!m || !sav_path) return fail("null argument");
    if (!m->rom_loaded) return fail("no ROM loaded");
    const u8* data = m->nds->NDSCartSlot.GetSaveMemory();
    u32 len = m->nds->NDSCartSlot.GetSaveMemoryLength();
    if (!data || len == 0) return 0;
    FILE* f = std::fopen(sav_path, "wb");
    if (!f) return fail(std::string("cannot write save: ") + sav_path);
    size_t n = std::fwrite(data, 1, len, f);
    std::fclose(f);
    if (n != len) return fail(std::string("short write: ") + sav_path);
    return 0;
}

int mds_reset(mds_t* m)
{
    g_last_error.clear();
    if (!m || !m->rom_loaded) return fail("no ROM loaded");
    boot(m);
    return 0;
}

uint32_t mds_run_frame(mds_t* m)
{
    if (!m || !m->rom_loaded) return 0;
    jit_thread_exec_mode();
    m->frames++;
    return m->nds->RunFrame();
}

uint64_t mds_frame_count(mds_t* m) { return m ? m->frames : 0; }

void mds_set_keys(mds_t* m, uint32_t pressed_mask)
{
    if (!m) return;
    m->keys = pressed_mask & 0xFFF;
    m->nds->SetKeyMask(~m->keys & 0xFFF);   // melonDS: 0 = pressed
}

uint32_t mds_get_keys(mds_t* m) { return m ? m->keys : 0; }

void mds_touch(mds_t* m, int x, int y)
{
    if (!m) return;
    if (x < 0) x = 0; if (x > 255) x = 255;
    if (y < 0) y = 0; if (y > 191) y = 191;
    m->nds->TouchScreen((u16)x, (u16)y);
}

void mds_release_touch(mds_t* m)
{
    if (m) m->nds->ReleaseScreen();
}

void mds_set_lid_closed(mds_t* m, int closed)
{
    if (m) m->nds->SetLidClosed(closed != 0);
}

static void bgra_to_rgba(const u32* src, uint8_t* dst)
{
    // melonDS framebuffer pixels are 0xAARRGGBB
    for (int i = 0; i < MDS_SCREEN_WIDTH * MDS_SCREEN_HEIGHT; i++)
    {
        u32 p = src[i];
        dst[i * 4 + 0] = (p >> 16) & 0xFF;
        dst[i * 4 + 1] = (p >> 8) & 0xFF;
        dst[i * 4 + 2] = p & 0xFF;
        dst[i * 4 + 3] = 0xFF;
    }
}

int mds_get_screens(mds_t* m, uint8_t* top_rgba, uint8_t* bottom_rgba)
{
    g_last_error.clear();
    if (!m) return fail("null instance");
    void* top = nullptr;
    void* bottom = nullptr;
    if (!m->nds->GPU.GetFramebuffers(&top, &bottom) || !top || !bottom)
        return fail("no framebuffer");
    if (top_rgba) bgra_to_rgba((const u32*)top, top_rgba);
    if (bottom_rgba) bgra_to_rgba((const u32*)bottom, bottom_rgba);
    return 0;
}

int mds_audio_available(mds_t* m)
{
    return m ? m->nds->SPU.GetOutputSize() : 0;
}

int mds_read_audio(mds_t* m, int16_t* out, int max_frames)
{
    if (!m || !out || max_frames <= 0) return 0;
    return m->nds->SPU.ReadOutput(out, max_frames);
}

int mds_save_state(mds_t* m, uint8_t** out, uint32_t* out_len)
{
    g_last_error.clear();
    if (!m || !out || !out_len) return fail("null argument");
    Savestate state;
    if (state.Error) return fail("cannot allocate savestate");
    if (!m->nds->DoSavestate(&state) || state.Error) return fail("savestate failed");
    state.Finish();
    u32 len = state.Length();
    auto* buf = (uint8_t*)std::malloc(len);
    if (!buf) return fail("out of memory");
    std::memcpy(buf, state.Buffer(), len);
    *out = buf;
    *out_len = len;
    return 0;
}

int mds_load_state(mds_t* m, const uint8_t* data, uint32_t len)
{
    g_last_error.clear();
    if (!m || !data) return fail("null argument");
    std::vector<u8> copy(data, data + len);   // Savestate wants a mutable buffer
    Savestate state(copy.data(), len, false);
    if (state.Error) return fail("invalid savestate");
    if (!m->nds->DoSavestate(&state) || state.Error) return fail("loading savestate failed");
    m->nds->SetKeyMask(~m->keys & 0xFFF);
    return 0;
}

void mds_free(void* p) { std::free(p); }

uint8_t  mds_read8(mds_t* m, uint32_t a)  { return m ? m->nds->ARM9Read8(a) : 0; }
uint16_t mds_read16(mds_t* m, uint32_t a) { return m ? m->nds->ARM9Read16(a) : 0; }
uint32_t mds_read32(mds_t* m, uint32_t a) { return m ? m->nds->ARM9Read32(a) : 0; }
void mds_write8(mds_t* m, uint32_t a, uint8_t v)   { if (m) m->nds->ARM9Write8(a, v); }
void mds_write16(mds_t* m, uint32_t a, uint16_t v) { if (m) m->nds->ARM9Write16(a, v); }
void mds_write32(mds_t* m, uint32_t a, uint32_t v) { if (m) m->nds->ARM9Write32(a, v); }

uint32_t mds_main_ram(mds_t* m, uint8_t** out)
{
    if (!m || !out) return 0;
    *out = m->nds->MainRAM;
    return m->nds->MainRAMMask + 1;
}

} // extern "C"
