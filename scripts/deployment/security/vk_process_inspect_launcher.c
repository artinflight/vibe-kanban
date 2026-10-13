/* Stable, no-argument sudo entrypoint. Source only; NOT setuid. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    (void)argv;
    if (argc != 1 || geteuid() != 0 || clearenv() != 0) {
        fputs("inspection blocked\n", stderr);
        return 1;
    }
    if (setenv("PATH", "/usr/bin:/bin", 1) != 0 || setenv("LANG", "C", 1) != 0) {
        return 1;
    }
    execl("/usr/bin/python3", "python3", "-I", "-S", "-B",
          "/usr/local/libexec/vk-process-inspection-v1.py", (char *)NULL);
    fputs("inspection blocked\n", stderr);
    return 1;
}
