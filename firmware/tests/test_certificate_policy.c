/* Standalone host mbedTLS verifier, NOT an ESP-IDF MQTT handshake or target test. */
#include "mbedtls/build_info.h"
#include "mbedtls/x509_crt.h"
#include <stdint.h>
#include <stdio.h>

#if !defined(MBEDTLS_HAVE_TIME) || !defined(MBEDTLS_HAVE_TIME_DATE)
#error "Host certificate regression requires mbedTLS date checks"
#endif

static int load(const char *path, mbedtls_x509_crt *cert) {
    FILE *file = fopen(path, "rb");
    if (!file) return -1;
    unsigned char bytes[8192];
    size_t size = fread(bytes, 1, sizeof(bytes) - 1, file);
    int invalid = ferror(file) || !feof(file);
    fclose(file);
    if (invalid) return -1;
    bytes[size] = 0;
    return mbedtls_x509_crt_parse(cert, bytes, size + 1);
}

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    mbedtls_x509_crt root, leaf;
    mbedtls_x509_crt_init(&root);
    mbedtls_x509_crt_init(&leaf);
    uint32_t flags = 0;
    int result = load(argv[1], &root) || load(argv[2], &leaf);
    if (!result) result = mbedtls_x509_crt_verify(&leaf, &root, NULL, argv[3], &flags, NULL, NULL);
    printf("flags=%u\n", (unsigned)flags);
    mbedtls_x509_crt_free(&root);
    mbedtls_x509_crt_free(&leaf);
    return result ? 1 : 0;
}
