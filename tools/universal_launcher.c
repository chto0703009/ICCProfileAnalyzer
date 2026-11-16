/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char executable[PATH_MAX];
    char resolved[PATH_MAX];
    uint32_t size = sizeof executable;
    if (_NSGetExecutablePath(executable, &size) || !realpath(executable, resolved)) {
        fputs("ICC Profile Analyzer: unable to locate the application bundle.\n", stderr);
        return 1;
    }
    char *filename = strrchr(resolved, '/');
    if (!filename) return 1;
    *filename = '\0';
#if defined(__arm64__)
    const char *label = "Apple Silicon";
#elif defined(__x86_64__)
    const char *label = "Intel";
#else
#error Unsupported architecture
#endif
    char target[PATH_MAX];
    int length = snprintf(target, sizeof target,
        "%s/../Helpers/ICC Profile Analyzer - %s.app/Contents/MacOS/ICC Profile Analyzer", resolved, label);
    if (length < 0 || (size_t)length >= sizeof target) return 1;
    argv[0] = target;
    execv(target, argv);
    perror("ICC Profile Analyzer: unable to start the native application");
    return 1;
}
