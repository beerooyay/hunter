// hunter_rt.c -- the thin C layer under the Praetor hunter.
//
// Praetor talks to the outside world through `extern fn` with scalars and raw pointers.
// This file supplies the few things the language/runtime doesn't have yet:
//   * a monotonic clock and per-thread CPU clock
//   * zeroed allocation with typed returns
//   * GMP integers as opaque handles (GMP's mpz_t is a struct; Praetor holds a pointer)
//   * the batched Fermat engine: a portable C reference implementation of exactly the
//     Montgomery algorithm the Metal kernel runs, so the GPU math can be validated on any
//     machine. On macOS with -DHUNTER_METAL the real GPU path lives in hunter_metal.m.
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <gmp.h>
#include <poll.h>
#include <spawn.h>
#include <signal.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/socket.h>


#include <sys/resource.h>
#ifdef __APPLE__
#include <libproc.h>
#endif
uint64_t rt_accounted_cpu_ns(void) {
    struct rusage a,b;
    getrusage(RUSAGE_SELF,&a); getrusage(RUSAGE_CHILDREN,&b);
    return ((uint64_t)a.ru_utime.tv_sec+a.ru_stime.tv_sec+b.ru_utime.tv_sec+b.ru_stime.tv_sec)*1000000000ull
       + ((uint64_t)a.ru_utime.tv_usec+a.ru_stime.tv_usec+b.ru_utime.tv_usec+b.ru_stime.tv_usec)*1000;
}
uint64_t rt_pid_cpu_ns(uint64_t pid) {
#ifdef __APPLE__
    struct rusage_info_v2 r;
    if(proc_pid_rusage((int)pid,RUSAGE_INFO_V2,(rusage_info_t*)&r)) return 0;
    return r.ri_user_time+r.ri_system_time;
#else
    char path[64],buf[4096];snprintf(path,sizeof(path),"/proc/%llu/stat",(unsigned long long)pid);
    FILE*f=fopen(path,"r");if(!f)return 0;
    if(!fgets(buf,sizeof(buf),f)){fclose(f);return 0;}fclose(f);
    char*p=strrchr(buf,')');if(!p)return 0;p+=2;
    /* fields 3..13 precede user/system ticks. */
    for(int i=3;i<14;i++){p=strchr(p,' ');if(!p)return 0;p++;}
    unsigned long long u,v;if(sscanf(p,"%llu %llu",&u,&v)!=2)return 0;
    return (u+v)*1000000000ull/(uint64_t)sysconf(_SC_CLK_TCK);
#endif
}
static unsigned char probe_selected[256];
uint64_t rt_probe_selected(uint64_t k) { return k<256 ? probe_selected[k] : 0; }
int rt_probe_request(uint64_t *v) {
    unsigned long long m,n,l,k;
    if(scanf("%llu %llu %llu %llu",&m,&n,&l,&k)!=4)return 0;
    if(n>256 || k>n)return 0;
    memset(probe_selected,0,sizeof(probe_selected));
    for(unsigned long long i=0;i<k;i++) {
        unsigned long long j;if(scanf("%llu",&j)!=1 || j>=n)return 0;
        probe_selected[j]=1;
    }
    v[0]=m;v[1]=n;v[2]=l;v[3]=k;return 1;
}

/* Fail closed on missing, expired or malformed cross-search calibration. */
uint64_t rt_shared_scale(uint64_t P, uint64_t d) {
    const uint64_t one = (uint64_t)1 << 32;
    FILE *f = fopen("learning/shared-scale.tsv", "r");
    if (!f) return one;
    unsigned long long p, den, expires; double scale;
    uint64_t result = one;
    while (fscanf(f, "%llu %llu %llu %lf", &p, &den, &expires, &scale) == 4) {
        if (p == P && den == d && expires > (unsigned long long)time(NULL) &&
            expires <= (unsigned long long)time(NULL) + 1800 &&
            isfinite(scale) && scale >= .95 && scale <= 1.05) {
            result = (uint64_t)llround(scale * (double)one); break;
        }
    }
    fclose(f); return result;
}
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

uint64_t rt_now_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}
uint64_t rt_cpu_ns(void) {
    struct timespec t; clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}
uint64_t rt_unix_s(void) { return (uint64_t)time(NULL); }
int64_t rt_ncpu(void) { long n = sysconf(_SC_NPROCESSORS_ONLN); return n > 0 ? n : 1; }

void *rt_alloc64(uint64_t n) { return calloc(n ? n : 1, 8); }
void *rt_alloc32(uint64_t n) { return calloc(n ? n : 1, 4); }
void *rt_alloc8(uint64_t n)  { return calloc(n ? n : 1, 1); }
void  rt_free(void *p) { free(p); }
void  rt_zero(void *p, uint64_t bytes) { memset(p, 0, bytes); }

void *rt_mpz(void) { mpz_ptr z = malloc(sizeof(__mpz_struct)); mpz_init(z); return z; }
void  rt_mpz_free(void *z) { mpz_clear((mpz_ptr)z); free(z); }
int   rt_mpz_odd(void *z) { return mpz_odd_p((mpz_ptr)z) ? 1 : 0; }

// ---------------------------------------------------------------- batched Fermat (base 2)
// numbers are packed as `nl` little-endian 32-bit limbs each. for every number n we test
// 2^(n-1) == 1 (mod n) using Montgomery multiplication with R = 2^(32*nl):
//   x = R mod n (Montgomery 1), then for each bit of n-1 from the top: x = mont(x,x);
//   if bit: x = 2x mod n (a doubling, no multiply). finally y = mont(x, 1) = 2^(n-1) mod n.
// R mod n arrives precomputed from the host (GMP), packed the same way.
static uint32_t inv32(uint32_t n0) {           // -n0^-1 mod 2^32 by Newton
    uint32_t x = n0;                            // correct to 3 bits for odd n0
    for (int i = 0; i < 5; i++) x *= 2 - n0 * x;
    return (uint32_t)(0u - x);
}
// t = a*b*R^-1 mod n (CIOS). t has nl+2 words of scratch; result left in r (nl words).
static void mont_mul(uint32_t *r, const uint32_t *a, const uint32_t *b, const uint32_t *n,
                     uint32_t ninv, int nl, uint32_t *t) {
    for (int i = 0; i < nl + 2; i++) t[i] = 0;
    for (int i = 0; i < nl; i++) {
        uint64_t c = 0;
        uint64_t ai = a[i];
        for (int j = 0; j < nl; j++) {
            uint64_t s = (uint64_t)t[j] + ai * b[j] + c;
            t[j] = (uint32_t)s; c = s >> 32;
        }
        uint64_t s = (uint64_t)t[nl] + c; t[nl] = (uint32_t)s; t[nl + 1] = (uint32_t)(s >> 32);
        uint32_t m = t[0] * ninv;
        c = ((uint64_t)t[0] + (uint64_t)m * n[0]) >> 32;
        for (int j = 1; j < nl; j++) {
            uint64_t s2 = (uint64_t)t[j] + (uint64_t)m * n[j] + c;
            t[j - 1] = (uint32_t)s2; c = s2 >> 32;
        }
        s = (uint64_t)t[nl] + c; t[nl - 1] = (uint32_t)s;
        t[nl] = t[nl + 1] + (uint32_t)(s >> 32);
    }
    // conditional subtract: if t >= n, t -= n
    int ge = t[nl] != 0;
    if (!ge) { ge = 1; for (int j = nl - 1; j >= 0; j--) { if (t[j] != n[j]) { ge = t[j] > n[j]; break; } } }
    if (ge) {
        int64_t br = 0;
        for (int j = 0; j < nl; j++) { int64_t d = (int64_t)t[j] - n[j] - br; r[j] = (uint32_t)d; br = d < 0; }
    } else {
        for (int j = 0; j < nl; j++) r[j] = t[j];
    }
}
static void mod_double(uint32_t *x, const uint32_t *n, int nl) {
    uint32_t carry = 0;
    for (int j = 0; j < nl; j++) { uint32_t v = x[j]; x[j] = (v << 1) | carry; carry = v >> 31; }
    int ge = carry != 0;
    if (!ge) { ge = 1; for (int j = nl - 1; j >= 0; j--) { if (x[j] != n[j]) { ge = x[j] > n[j]; break; } } }
    if (ge) { int64_t br = 0; for (int j = 0; j < nl; j++) { int64_t d = (int64_t)x[j] - n[j] - br; x[j] = (uint32_t)d; br = d < 0; } }
}
// returns 1 = probable prime (base 2), 0 = composite
int rt_fermat_one(const uint32_t *n, const uint32_t *rmodn, int nl) {
    uint32_t *x = malloc(4 * (3 * nl + 2)), *one = x + nl, *t = one + nl;
    memcpy(x, rmodn, 4 * nl);
    uint32_t ninv = inv32(n[0]);
    int top = nl - 1; while (top > 0 && n[top] == 0) top--;
    int bit = 31; while (bit > 0 && !((n[top] >> bit) & 1)) bit--;
    // exponent e = n-1: n is odd, so n-1 differs only in bit 0
    for (int w = top; w >= 0; w--) {
        for (int b = (w == top ? bit : 31); b >= 0; b--) {
            mont_mul(x, x, x, n, ninv, nl, t);
            uint32_t eb = (w == 0 && b == 0) ? 0 : ((n[w] >> b) & 1);
            if (eb) mod_double(x, n, nl);
        }
    }
    memset(one, 0, 4 * nl); one[0] = 1;
    mont_mul(x, x, one, n, ninv, nl, t);       // leave Montgomery domain
    int ok = x[0] == 1; for (int j = 1; j < nl && ok; j++) ok = x[j] == 0;
    free(x);
    return ok;
}

// CPU reference for the batched kernel: same packing, same math. used for validation, and as
// the stand-in "gpu" on machines without Metal so the wavefront code path is always exercised.
int rt_cpu_fermat_batch(const uint32_t *nums, const uint32_t *rmods, int nl, int count, uint8_t *out) {
    for (int i = 0; i < count; i++) out[i] = (uint8_t)rt_fermat_one(nums + (size_t)i * nl, rmods + (size_t)i * nl, nl);
    return 0;
}
// exact fallback with GMP: same answer as the GPU (2^(n-1) mod n == 1), ~15x faster than the
// Montgomery reference above. used whenever a GPU batch fails.
int rt_gmp_fermat_batch(const uint32_t *nums, const uint32_t *rmods, int nl, int count, uint8_t *out) {
    (void)rmods;
    mpz_t n, e, r, two;
    mpz_init(n); mpz_init(e); mpz_init(r); mpz_init_set_ui(two, 2);
    for (int i = 0; i < count; i++) {
        mpz_import(n, (size_t)nl, -1, 4, 0, 0, nums + (size_t)i * nl);
        mpz_sub_ui(e, n, 1);
        mpz_powm(r, two, e, n);
        out[i] = mpz_cmp_ui(r, 1) == 0 ? 1 : 0;
    }
    mpz_clear(n); mpz_clear(e); mpz_clear(r); mpz_clear(two);
    return 0;
}
#ifndef HUNTER_METAL
void rt_gpu_set_budget_ms(int ms) { (void)ms; }
int rt_gpu_available(void) { return 0; }
const char *rt_gpu_name(void) { return "none (cpu reference stands in)"; }
const char *rt_gpu_error(void) { return ""; }
void rt_gpu_set_mode(int m) { (void)m; }
int rt_gpu_fermat_batch(const uint32_t *nums, const uint32_t *rmods, int nl, int count, uint8_t *out) {
    return rt_cpu_fermat_batch(nums, rmods, nl, count, out);
}
#endif
uint64_t rt_strlen(const char *s) { return (uint64_t)strlen(s); }
int rt_mpz_bits(void *z) { return (int)mpz_sizeinbase((mpz_ptr)z, 2); }

// pack mpz n (and R mod n) into nl 32-bit limbs; returns 0 if it doesn't fit
int rt_pack(void *zn, uint32_t *dst_n, uint32_t *dst_r, int nl) {
    mpz_ptr n = (mpz_ptr)zn;
    size_t cnt = 0;
    if (mpz_sizeinbase(n, 2) > (size_t)nl * 32) return 0;
    memset(dst_n, 0, 4 * nl); memset(dst_r, 0, 4 * nl);
    mpz_export(dst_n, &cnt, -1, 4, 0, 0, n);
    mpz_t R; mpz_init(R); mpz_setbit(R, (mp_bitcnt_t)nl * 32); mpz_mod(R, R, n);
    mpz_export(dst_r, &cnt, -1, 4, 0, 0, R); mpz_clear(R);
    return 1;
}

// ---------------------------------------------------------------- server glue (hunter serve)
// the control room's logic is Praetor; these are the syscalls it needs that std doesn't wrap yet:
// poll-with-timeout accept, fork/exec of worker processes, non-blocking reap, signals, pread.
extern char **environ;
void rt_cloexec(int64_t fd);
static volatile sig_atomic_t g_quit = 0;
static void on_quit(int s) { (void)s; g_quit = 1; }
void rt_server_init(void) {
    signal(SIGPIPE, SIG_IGN);                 // a browser closing a tab must not kill the hunt
    signal(SIGINT, on_quit); signal(SIGTERM, on_quit);
}
int rt_quit_requested(void) { return g_quit ? 1 : 0; }
int rt_is_darwin(void) {
#ifdef __APPLE__
    return 1;
#else
    return 0;
#endif
}
int64_t rt_getpid(void) { return (int64_t)getpid(); }

static int self_path(char *buf, size_t cap) {
#ifdef __APPLE__
    uint32_t sz = (uint32_t)cap;
    if (_NSGetExecutablePath(buf, &sz) != 0) return -1;
    char rp[4096];
    if (realpath(buf, rp)) snprintf(buf, cap, "%s", rp);
    return 0;
#else
    ssize_t n = readlink("/proc/self/exe", buf, cap - 1);
    if (n <= 0) return -1;
    buf[n] = 0; return 0;
#endif
}
// what to exec for a worker: on linux /proc/self/exe stays valid even if the binary is rebuilt
// underneath a running server (the path would point at a deleted file)
static int exec_path(char *buf, size_t cap) {
#ifdef __APPLE__
    return self_path(buf, cap);
#else
    snprintf(buf, cap, "/proc/self/exe");
    return 0;
#endif
}
int rt_chdir_exe(void) {
    char b[4096];
    if (self_path(b, sizeof b)) return -1;
    char *sl = strrchr(b, '/');
    if (!sl) return -1;
    *sl = 0;
    return chdir(b);
}

// wait up to ms for a connection; -1 on timeout or signal
int64_t rt_accept_ms(int64_t fd, int ms) {
    struct pollfd p; p.fd = (int)fd; p.events = POLLIN; p.revents = 0;
    if (poll(&p, 1, ms) <= 0) return -1;
    int c = accept((int)fd, NULL, NULL);
    if (c >= 0) rt_cloexec(c);
    return (int64_t)c;
}
// recv with a timeout; returns bytes, 0 on close, -1 on timeout/error
int64_t rt_recv_ms(int64_t fd, uint8_t *buf, uint64_t n, int ms) {
    struct pollfd p; p.fd = (int)fd; p.events = POLLIN; p.revents = 0;
    if (poll(&p, 1, ms) <= 0) return -1;
    return (int64_t)recv((int)fd, buf, n, 0);
}
int64_t rt_send_all(int64_t fd, const uint8_t *buf, uint64_t n) {
    uint64_t off = 0;
    while (off < n) {
        ssize_t w = send((int)fd, buf + off, n - off, 0);
        if (w <= 0) return -1;
        off += (uint64_t)w;
    }
    return (int64_t)off;
}
void rt_close_fd(int64_t fd) { close((int)fd); }

// argz: nargs NUL-terminated strings back to back; envz: nenv "K=V" strings back to back.
// self=1 runs this same executable. stdout+stderr go to `out` (truncated). returns the pid.
// posix_spawn, not fork: once Metal is up the server is multithreaded, and malloc in a forked child
// can deadlock on macOS. every fd the server holds is close-on-exec, so workers inherit nothing.
int64_t rt_spawn(const char *argz, int nargs, int self, const char *envz, int nenv, const char *out) {
    char *argv[64];
    const char *p = argz;
    if (nargs > 62) nargs = 62;
    for (int i = 0; i < nargs; i++) { argv[i] = (char *)p; p += strlen(p) + 1; }
    argv[nargs] = NULL;
    char exe[4096];
    if (self && exec_path(exe, sizeof exe)) return -1;
    size_t ne = 0;
    while (environ[ne]) ne++;
    char **envp = malloc((ne + (size_t)nenv + 1) * sizeof(char *));
    if (!envp) return -1;
    size_t k = 0;
    const char *e = envz;
    for (int i = 0; i < nenv; i++) { envp[k++] = (char *)e; e += strlen(e) + 1; }   // ours first: getenv takes the first match
    for (size_t i = 0; i < ne; i++) envp[k++] = environ[i];
    envp[k] = NULL;
    posix_spawn_file_actions_t fa;
    posix_spawn_file_actions_init(&fa);
    posix_spawn_file_actions_addopen(&fa, 1, out, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    posix_spawn_file_actions_adddup2(&fa, 1, 2);
    posix_spawn_file_actions_addopen(&fa, 0, "/dev/null", O_RDONLY, 0);
    pid_t pid = 0;
    int rc = self ? posix_spawn(&pid, exe, &fa, NULL, argv, envp)
                  : posix_spawnp(&pid, argv[0], &fa, NULL, argv, envp);
    posix_spawn_file_actions_destroy(&fa);
    free(envp);
    return rc == 0 ? (int64_t)pid : -1;
}
void rt_cloexec(int64_t fd) { int f = fcntl((int)fd, F_GETFD); if (f >= 0) fcntl((int)fd, F_SETFD, f | FD_CLOEXEC); }
// -1 still running, else exit code (128+signal if killed)
int rt_reap(int64_t pid) {
    int st = 0;
    pid_t r = waitpid((pid_t)pid, &st, WNOHANG);
    if (r == 0) return -1;
    if (r < 0) return 255;
    if (WIFEXITED(st)) return WEXITSTATUS(st);
    if (WIFSIGNALED(st)) return 128 + WTERMSIG(st);
    return 255;
}
void rt_kill(int64_t pid, int sig) { if (pid > 0) kill((pid_t)pid, sig); }

// files
int64_t rt_open_r(const char *path) { return (int64_t)open(path, O_RDONLY | O_CLOEXEC); }
int64_t rt_read_fd(int64_t fd, uint8_t *buf, uint64_t n) { return (int64_t)read((int)fd, buf, n); }
int64_t rt_file_size(const char *path) { struct stat st; if (stat(path, &st)) return -1; return (int64_t)st.st_size; }
int64_t rt_read_at(const char *path, uint64_t off, uint8_t *buf, uint64_t n) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    ssize_t r = pread(fd, buf, n, (off_t)off);
    close(fd);
    return (int64_t)r;
}
int rt_append(const char *path, const uint8_t *buf, uint64_t n) {
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return -1;
    ssize_t w = write(fd, buf, n);
    close(fd);
    return w == (ssize_t)n ? 0 : -1;
}
int rt_write_atomic(const char *path, const uint8_t *buf, uint64_t n) {   // write tmp, then rename
    char tmp[4096];
    snprintf(tmp, sizeof tmp, "%s.tmp", path);
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    ssize_t w = write(fd, buf, n);
    close(fd);
    if (w != (ssize_t)n) return -1;
    return rename(tmp, path);
}
int rt_rename(const char *a, const char *b) { return rename(a, b); }
int rt_mkdir(const char *p) { return mkdir(p, 0755); }
uint64_t rt_date(char *buf) {      // local "YYYY-MM-DD HH:MM"
    time_t t = time(NULL);
    struct tm tm; localtime_r(&t, &tm);
    return (uint64_t)strftime(buf, 32, "%Y-%m-%d %H:%M", &tm);
}
void rt_sleep_ms(int ms) { usleep((useconds_t)ms * 1000); }

/* Finite-window model: both nearest prime endpoints must be in the sieve. */
double rt_logtarget(double q, uint64_t gap, const uint32_t *right, uint64_t nr,
                    const uint32_t *left, uint64_t nl) {
    if (!(q > 0 && q < 1)) return NAN;
    double loss = log1p(-q), total = -INFINITY;
    for (uint64_t i = 0; i < nr; ++i) {
        uint64_t lo = 0, hi = nl;
        int64_t need = (int64_t)gap - right[i];
        while (lo < hi) {
            uint64_t mid = lo + (hi - lo) / 2;
            if ((int64_t)left[mid] < need) lo = mid + 1; else hi = mid;
        }
        if (lo == nl) continue;
        double term = log(q) + i * loss + lo * loss
                    + log(-expm1((nl - lo) * loss));
        if (!isfinite(total)) total = term;
        else {
            double top = fmax(total, term);
            total = top + log1p(exp(fmin(total, term) - top));
        }
    }
    return total;
}

void rt_probe(uint64_t m, uint64_t q62, uint64_t ln32, uint64_t target,
              const uint32_t *right, uint64_t nr, const uint32_t *left,
              uint64_t nl, uint64_t nanos) {
    double q = ldexp((double)q62, -62), ln = ldexp((double)ln32, -32);
    double total = rt_logtarget(q, (uint64_t)ceil(target * ln), right, nr, left, nl);
    double loss = log1p(-q);
    double tests = (-expm1(nr * loss) - expm1(nl * loss)) / q;
    double seconds = tests * nanos / 1e9;
    printf("%llu\t%.9f\t%.6f\t%.9f\n", (unsigned long long)m,
           total / log(10.0), tests,
           seconds > 0 ? (total + log(3600 / seconds)) / log(10.0) : -INFINITY);
    if (getenv("HUNTER_PATTERNS") && !strcmp(getenv("HUNTER_PATTERNS"), "1"))
        printf("@meta\t%llu\t%.17g\t%.17g\n", (unsigned long long)m, q, ln);
    fflush(stdout);
}

void rt_pattern(uint64_t m, const uint32_t *right, uint64_t nr,
                const uint32_t *left, uint64_t nl) {
    printf("@\t%llu\t", (unsigned long long)m);
    for (uint64_t i = 0; i < nr; ++i) printf("%s%u", i ? "," : "", right[i]);
    putchar('\t');
    for (uint64_t i = 0; i < nl; ++i) printf("%s%u", i ? "," : "", left[i]);
    putchar('\n');
    fflush(stdout);
}

#include "survivors.h"
uint64_t rt_survivors(const uint64_t *bits, uint64_t start, uint64_t limit, uint32_t *out) {
    return hunter_survivors(bits, start, limit, out);
}
