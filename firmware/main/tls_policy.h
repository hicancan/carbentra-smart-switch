#ifndef CARBENTRA_SWITCH_TLS_POLICY_H
#define CARBENTRA_SWITCH_TLS_POLICY_H

#include "sdkconfig.h"
#include "mbedtls/build_info.h"

/* Check both ESP-IDF's selected options and the effective mbedTLS config.
 * Waiting for SNTP cannot compensate for a library built without date checks. */
#if !defined(CONFIG_MBEDTLS_HAVE_TIME) || !CONFIG_MBEDTLS_HAVE_TIME || \
    !defined(CONFIG_MBEDTLS_HAVE_TIME_DATE) || !CONFIG_MBEDTLS_HAVE_TIME_DATE
#error "Switch TLS requires ESP-IDF certificate date verification"
#endif
#if !defined(MBEDTLS_HAVE_TIME) || !defined(MBEDTLS_HAVE_TIME_DATE)
#error "Switch TLS requires effective mbedTLS certificate date verification"
#endif
#if defined(CONFIG_ESP_TLS_INSECURE) && CONFIG_ESP_TLS_INSECURE
#error "Switch TLS must not permit insecure server verification"
#endif

#endif
