/* Freestanding Linux AArch64 framebuffer probe. No libc or host shims.
 * Uses the Linux UAPI framebuffer layout and AArch64 syscall ABI.
 * Writes through mmap so DRM's deferred-I/O damage tracking observes pixels.
 */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned long u64;
struct bitfield { u32 offset, length, msb_right; };
struct var_info {
    u32 xres, yres, xvirtual, yvirtual, xoffset, yoffset, bpp, grayscale;
    struct bitfield red, green, blue, transparency;
    u32 nonstd, activate, height, width, accel_flags, pixclock;
    u32 left, right, upper, lower, hsync, vsync, sync, vmode, rotate, colorspace;
    u32 reserved[4];
};
struct fix_info {
    char id[16];
    u64 smem_start;
    u32 smem_len, type, type_aux, visual;
    u16 xpanstep, ypanstep, ywrapstep;
    u32 line_length;
    u64 mmio_start;
    u32 mmio_len, accel;
    u16 capabilities, reserved[2];
};
_Static_assert(sizeof(struct var_info) == 160, "Linux fb_var_screeninfo ABI");
_Static_assert(sizeof(struct fix_info) == 80, "Linux fb_fix_screeninfo ABI");

static long syscall6(long n, long a, long b, long c, long d, long e, long f) {
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x4 __asm__("x4") = e;
    register long x5 __asm__("x5") = f;
    register long x8 __asm__("x8") = n;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5), "r"(x8) : "memory", "cc");
    return x0;
}
static long ioctl(long fd, long request, long data) { return syscall6(29, fd, request, data, 0, 0, 0); }
static struct var_info variable;
static struct fix_info fixed;

long probe_main(u64 *stack) {
    if (stack[0] != 2) return 10;
    const char *phase_arg = (const char *)stack[2];
    if ((phase_arg[0] != '0' && phase_arg[0] != '1') || phase_arg[1]) return 11;
    unsigned phase = (unsigned)(phase_arg[0] - '0');
    long fd = syscall6(56, -100, (long)"/dev/fb0", 2, 0, 0, 0);
    if (fd < 0) return 12;
    if (ioctl(fd, 0x4600, (long)&variable) < 0 || ioctl(fd, 0x4602, (long)&fixed) < 0) return 13;
    if (variable.xres != 800 || variable.yres != 600 || variable.bpp != 32 ||
        variable.xoffset || variable.yoffset || fixed.line_length != 3200 ||
        fixed.smem_len < 1920000 || fixed.smem_len > 16 * 1024 * 1024 ||
        variable.red.offset != 16 || variable.green.offset != 8 || variable.blue.offset != 0 ||
        variable.red.length != 8 || variable.green.length != 8 || variable.blue.length != 8) return 14;
    long address = syscall6(222, 0, fixed.smem_len, 3, 1, fd, 0);
    if (address < 0 && address >= -4095) return 15;
    volatile u32 *pixels = (volatile u32 *)address;
    const u32 colors[4] = {0xffcc3322, 0xff44cc33, 0xff2255cc, 0xffcccccc};
    for (unsigned y = 0; y < 600; ++y)
        for (unsigned x = 0; x < 800; ++x)
            pixels[y * 800 + x] = colors[((y / 300) * 2 + x / 400 + phase) % 4];
    if (syscall6(227, address, fixed.smem_len, 4, 0, 0, 0) < 0) return 16; /* msync */
    if (ioctl(fd, 0x4606, (long)&variable) < 0) return 17; /* pan/commit scanout */
    if (ioctl(fd, 0x4611, 0) < 0) return 18; /* unblank */
    const char message[] = "IDECK_FB_MMAP_WRITE_OK\n";
    syscall6(64, 1, (long)message, sizeof(message) - 1, 0, 0, 0);
    syscall6(215, address, fixed.smem_len, 0, 0, 0, 0); /* munmap */
    syscall6(57, fd, 0, 0, 0, 0, 0); /* close */
    return 0;
}

__asm__(".text\n.global _start\n.type _start,%function\n_start:\n"
        "mov x0, sp\nbl probe_main\nmov x8, #93\nsvc #0\n");
