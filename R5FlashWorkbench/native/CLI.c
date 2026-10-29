/* Relocatable macOS CLI launcher; preserves argv without shell interpretation. */
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    uint32_t size = 0;
    _NSGetExecutablePath(NULL, &size);
    char *buffer = malloc(size);
    if (!buffer || _NSGetExecutablePath(buffer, &size)) return 1;
    char *base = realpath(buffer, NULL);
    free(buffer);
    if (!base) { perror("r5wb executable path"); return 1; }
    char *slash = strrchr(base, '/');
    if (!slash) { free(base); return 1; }
    *slash = '\0';
    char *python = NULL, *script = NULL;
    if (asprintf(&python, "%s/../Resources/python/bin/python3.12", base) < 0 ||
        asprintf(&script, "%s/../Resources/engine/assistant.py", base) < 0) return 1;
    char **args = calloc((size_t)argc + 4, sizeof(char *));
    if (!args) return 1;
    args[0] = python; args[1] = "-I"; args[2] = "-B"; args[3] = script;
    for (int i = 1; i < argc; ++i) args[i + 3] = argv[i];
    execv(python, args);
    perror("r5wb bundled Python");
    return 1;
}
