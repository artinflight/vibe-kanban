/* Fixed metadata-only root entrypoint. No caller argv or inherited Python env. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(int argc, char **argv) {
    (void)argv;
    if (argc != 1 || geteuid() != 0) return 1;
    if (clearenv() || setenv("PATH", "/usr/bin:/bin", 1)) return 1;
    execl("/usr/bin/python3", "python3", "-I", "-S", "-B",
          "/usr/local/libexec/vk-workspace-archive-inspection-v1.py", (char *)0);
    return 1;
}
