// Thin C API over the melonDS core, meant to be loaded with Python ctypes.
// All functions returning int use 0 = success, -1 = error (see mds_last_error).
#ifndef MELONDS_SHIM_H
#define MELONDS_SHIM_H

#include <stdint.h>

#if defined(_WIN32)
#  define MDS_API __declspec(dllexport)
#else
#  define MDS_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define MDS_SCREEN_WIDTH  256
#define MDS_SCREEN_HEIGHT 192

// Key bits for mds_set_keys (1 = pressed)
#define MDS_KEY_A      (1u << 0)
#define MDS_KEY_B      (1u << 1)
#define MDS_KEY_SELECT (1u << 2)
#define MDS_KEY_START  (1u << 3)
#define MDS_KEY_RIGHT  (1u << 4)
#define MDS_KEY_LEFT   (1u << 5)
#define MDS_KEY_UP     (1u << 6)
#define MDS_KEY_DOWN   (1u << 7)
#define MDS_KEY_R      (1u << 8)
#define MDS_KEY_L      (1u << 9)
#define MDS_KEY_X      (1u << 10)
#define MDS_KEY_Y      (1u << 11)

typedef struct mds_t mds_t;

// Last error message of the calling thread ("" if none).
MDS_API const char* mds_last_error(void);

// Minimum level printed to stderr: 0 debug, 1 info, 2 warn (default), 3 error, 4 silent.
MDS_API void mds_set_log_level(int level);

// Create an emulator instance.
// bios9/bios7/firmware: paths to dumps, or NULL to use FreeBIOS / generated firmware.
// use_jit: 1 to enable the JIT recompiler.
MDS_API mds_t* mds_create(const char* bios9, const char* bios7, const char* firmware, int use_jit);
MDS_API void mds_destroy(mds_t* m);

// Load a .nds ROM and boot it. sav_path may be NULL; if it points to an existing
// file, that battery save is loaded. Nothing is written back automatically.
MDS_API int mds_load_rom(mds_t* m, const char* rom_path, const char* sav_path);

// Same, but the ROM comes from memory (data is copied).
MDS_API int mds_load_rom_mem(mds_t* m, const uint8_t* data, uint32_t len, const char* sav_path);

// Write the cartridge's battery save memory to a file.
// Returns 0 on success (also when the cart has no save memory), -1 on error.
MDS_API int mds_write_save(mds_t* m, const char* sav_path);

// Reset and reboot the currently loaded ROM.
MDS_API int mds_reset(mds_t* m);

// Emulate one frame. Returns the number of scanlines run.
MDS_API uint32_t mds_run_frame(mds_t* m);

// Frames run since the ROM was loaded.
MDS_API uint64_t mds_frame_count(mds_t* m);

// Input
MDS_API void mds_set_keys(mds_t* m, uint32_t pressed_mask);
MDS_API uint32_t mds_get_keys(mds_t* m);
MDS_API void mds_touch(mds_t* m, int x, int y);   // bottom screen, 0..255 x 0..191
MDS_API void mds_release_touch(mds_t* m);
MDS_API void mds_set_lid_closed(mds_t* m, int closed);

// Copy the last finished frame. Each buffer must hold 256*192*4 bytes.
// Pixel format: RGBA8888. Either pointer may be NULL.
MDS_API int mds_get_screens(mds_t* m, uint8_t* top_rgba, uint8_t* bottom_rgba);

// Audio: interleaved stereo s16 at 48000 Hz. Returns stereo frames read.
MDS_API int mds_audio_available(mds_t* m);
MDS_API int mds_read_audio(mds_t* m, int16_t* out, int max_frames);

// Savestates (in memory). mds_save_state allocates *out; free it with mds_free.
MDS_API int mds_save_state(mds_t* m, uint8_t** out, uint32_t* out_len);
MDS_API int mds_load_state(mds_t* m, const uint8_t* data, uint32_t len);
MDS_API void mds_free(void* p);

// Memory access (ARM9 bus).
MDS_API uint8_t  mds_read8(mds_t* m, uint32_t addr);
MDS_API uint16_t mds_read16(mds_t* m, uint32_t addr);
MDS_API uint32_t mds_read32(mds_t* m, uint32_t addr);
MDS_API void mds_write8(mds_t* m, uint32_t addr, uint8_t val);
MDS_API void mds_write16(mds_t* m, uint32_t addr, uint16_t val);
MDS_API void mds_write32(mds_t* m, uint32_t addr, uint32_t val);

// Direct pointer to main RAM (4 MB on DS). Returns size, writes pointer to *out.
MDS_API uint32_t mds_main_ram(mds_t* m, uint8_t** out);

#ifdef __cplusplus
}
#endif

#endif
