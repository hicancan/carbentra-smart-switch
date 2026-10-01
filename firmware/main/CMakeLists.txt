idf_component_register(SRCS "app_main.c" "network.c" "device_config.c" "command_json.c" "../core/switch_core.c" "../core/meter.c"
    INCLUDE_DIRS "." "../core"
    REQUIRES driver esp_timer esp_wifi esp_event esp_netif nvs_flash mqtt json mbedtls wifi_provisioning esp_hw_support lwip bootloader_support)
