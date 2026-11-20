// Headless implementation of melonDS's Platform interface for the Python shim.
#include "Platform.h"
#include "melonds_shim.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdio>
#include <mutex>
#include <thread>

#include <sys/stat.h>
#if !defined(_WIN32)
#include <dlfcn.h>
#include <unistd.h>
#endif

static std::atomic<int> g_log_level{2};

extern "C" MDS_API void mds_set_log_level(int level) { g_log_level = level; }

namespace melonDS::Platform
{

void SignalStop(StopReason, void*) {}

// ---- files ---------------------------------------------------------------

std::string GetLocalFilePath(const std::string& filename) { return filename; }

FileHandle* OpenFile(const std::string& path, FileMode mode)
{
    if ((mode & (Read | Write)) == None) return nullptr;

    bool exists = FileExists(path);
    if ((mode & Write) && (mode & NoCreate) && !exists) return nullptr;
    if (!(mode & Write) && !exists) return nullptr;

    std::string m;
    if (mode & Append)
        m = (mode & Read) ? "a+" : "a";
    else if (mode & Write)
    {
        if ((mode & Preserve) && exists)
            m = "r+";
        else
            m = (mode & Read) ? "w+" : "w";
    }
    else
        m = "r";
    if (!(mode & Text)) m += "b";

    return reinterpret_cast<FileHandle*>(std::fopen(path.c_str(), m.c_str()));
}

FileHandle* OpenLocalFile(const std::string& path, FileMode mode) { return OpenFile(path, mode); }

bool FileExists(const std::string& name)
{
    struct stat st;
    return stat(name.c_str(), &st) == 0;
}

bool LocalFileExists(const std::string& name) { return FileExists(name); }

bool CheckFileWritable(const std::string& filepath)
{
    FileHandle* f = OpenFile(filepath, FileMode::Append);
    if (!f) return false;
    CloseFile(f);
    return true;
}

bool CheckLocalFileWritable(const std::string& filepath) { return CheckFileWritable(filepath); }

static FILE* F(FileHandle* f) { return reinterpret_cast<FILE*>(f); }

bool CloseFile(FileHandle* file) { return std::fclose(F(file)) == 0; }
bool IsEndOfFile(FileHandle* file) { return std::feof(F(file)) != 0; }
bool FileReadLine(char* str, int count, FileHandle* file) { return std::fgets(str, count, F(file)) != nullptr; }
u64 FilePosition(FileHandle* file) { return (u64)std::ftell(F(file)); }

bool FileSeek(FileHandle* file, s64 offset, FileSeekOrigin origin)
{
    int o = SEEK_SET;
    if (origin == FileSeekOrigin::Current) o = SEEK_CUR;
    else if (origin == FileSeekOrigin::End) o = SEEK_END;
    return std::fseek(F(file), (long)offset, o) == 0;
}

void FileRewind(FileHandle* file) { std::rewind(F(file)); }
u64 FileRead(void* data, u64 size, u64 count, FileHandle* file) { return std::fread(data, size, count, F(file)); }
bool FileFlush(FileHandle* file) { return std::fflush(F(file)) == 0; }
u64 FileWrite(const void* data, u64 size, u64 count, FileHandle* file) { return std::fwrite(data, size, count, F(file)); }

u64 FileWriteFormatted(FileHandle* file, const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    int r = std::vfprintf(F(file), fmt, args);
    va_end(args);
    return r < 0 ? 0 : (u64)r;
}

u64 FileLength(FileHandle* file)
{
    FILE* f = F(file);
    long pos = std::ftell(f);
    std::fseek(f, 0, SEEK_END);
    long len = std::ftell(f);
    std::fseek(f, pos, SEEK_SET);
    return len < 0 ? 0 : (u64)len;
}

// ---- logging -------------------------------------------------------------

void Log(LogLevel level, const char* fmt, ...)
{
    if ((int)level < g_log_level.load()) return;
    va_list args;
    va_start(args, fmt);
    std::vfprintf(stderr, fmt, args);
    va_end(args);
}

// ---- threads -------------------------------------------------------------

struct Thread { std::thread t; };

Thread* Thread_Create(std::function<void()> func)
{
    auto* th = new Thread;
    th->t = std::thread(std::move(func));
    return th;
}

void Thread_Free(Thread* thread)
{
    if (!thread) return;
    if (thread->t.joinable()) thread->t.detach();
    delete thread;
}

void Thread_Wait(Thread* thread)
{
    if (thread && thread->t.joinable()) thread->t.join();
}

struct Semaphore
{
    std::mutex m;
    std::condition_variable cv;
    int count = 0;
};

Semaphore* Semaphore_Create() { return new Semaphore; }
void Semaphore_Free(Semaphore* s) { delete s; }

void Semaphore_Reset(Semaphore* s)
{
    std::lock_guard<std::mutex> lk(s->m);
    s->count = 0;
}

void Semaphore_Wait(Semaphore* s)
{
    std::unique_lock<std::mutex> lk(s->m);
    s->cv.wait(lk, [s] { return s->count > 0; });
    s->count--;
}

bool Semaphore_TryWait(Semaphore* s, int timeout_ms)
{
    std::unique_lock<std::mutex> lk(s->m);
    if (timeout_ms == 0)
    {
        if (s->count == 0) return false;
    }
    else if (!s->cv.wait_for(lk, std::chrono::milliseconds(timeout_ms), [s] { return s->count > 0; }))
        return false;
    s->count--;
    return true;
}

void Semaphore_Post(Semaphore* s, int count)
{
    {
        std::lock_guard<std::mutex> lk(s->m);
        s->count += count;
    }
    s->cv.notify_all();
}

struct Mutex { std::mutex m; };

Mutex* Mutex_Create() { return new Mutex; }
void Mutex_Free(Mutex* m) { delete m; }
void Mutex_Lock(Mutex* m) { m->m.lock(); }
void Mutex_Unlock(Mutex* m) { m->m.unlock(); }
bool Mutex_TryLock(Mutex* m) { return m->m.try_lock(); }

void Sleep(u64 usecs) { std::this_thread::sleep_for(std::chrono::microseconds(usecs)); }

u64 GetMSCount()
{
    using namespace std::chrono;
    return (u64)duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

u64 GetUSCount()
{
    using namespace std::chrono;
    return (u64)duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count();
}

// ---- saves ---------------------------------------------------------------

// Battery saves are written explicitly with mds_write_save (PyBoy-style: on stop).
void WriteNDSSave(const u8*, u32, u32, u32, void*) {}

void WriteGBASave(const u8*, u32, u32, u32, void*) {}
void WriteFirmware(const Firmware&, u32, u32, void*) {}
void WriteDateTime(int, int, int, int, int, int, void*) {}

// ---- local multiplayer / network (unsupported) ---------------------------

void MP_Begin(void*) {}
void MP_End(void*) {}
int MP_SendPacket(u8*, int, u64, void*) { return 0; }
int MP_RecvPacket(u8*, u64*, void*) { return 0; }
int MP_SendCmd(u8*, int, u64, void*) { return 0; }
int MP_SendReply(u8*, int, u64, u16, void*) { return 0; }
int MP_SendAck(u8*, int, u64, void*) { return 0; }
int MP_RecvHostPacket(u8*, u64*, void*) { return 0; }
u16 MP_RecvReplies(u8*, u64, u16, void*) { return 0; }

int Net_SendPacket(u8*, int, void*) { return 0; }
int Net_RecvPacket(u8*, void*) { return 0; }

// ---- camera / mic (unsupported) ------------------------------------------

void Camera_Start(int, void*) {}
void Camera_Stop(int, void*) {}
void Camera_CaptureFrame(int, u32* frame, int width, int height, bool, void*)
{
    for (int i = 0; i < width * height; i++) frame[i] = 0;
}

void Mic_Start(void*) {}
void Mic_Stop(void*) {}
int Mic_ReadInput(s16*, int, void*) { return 0; }

// ---- AAC (DSi only, unsupported) -----------------------------------------

AACDecoder* AAC_Init() { return nullptr; }
void AAC_DeInit(AACDecoder*) {}
bool AAC_Configure(AACDecoder*, int, int) { return false; }
bool AAC_DecodeFrame(AACDecoder*, const void*, int, void*, int) { return false; }

// ---- addons --------------------------------------------------------------

bool Addon_KeyDown(KeyType, void*) { return false; }
void Addon_RumbleStart(u32, void*) {}
void Addon_RumbleStop(void*) {}
float Addon_MotionQuery(MotionQueryType type, void*)
{
    // resting flat: gravity on Z
    return type == MotionAccelerationZ ? 9.80665f : 0.0f;
}

// ---- dynamic libraries ---------------------------------------------------

DynamicLibrary* DynamicLibrary_Load(const char* lib)
{
#if !defined(_WIN32)
    return reinterpret_cast<DynamicLibrary*>(dlopen(lib, RTLD_NOW | RTLD_LOCAL));
#else
    return nullptr;
#endif
}

void DynamicLibrary_Unload(DynamicLibrary* lib)
{
#if !defined(_WIN32)
    if (lib) dlclose(lib);
#endif
}

void* DynamicLibrary_LoadFunction(DynamicLibrary* lib, const char* name)
{
#if !defined(_WIN32)
    return lib ? dlsym(lib, name) : nullptr;
#else
    return nullptr;
#endif
}

} // namespace melonDS::Platform
