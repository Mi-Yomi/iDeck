/* Own audit probe for the pinned Madeira/Wine GnuTLS interface.
 * GENERATED FROM gnutls-symbol-lock.json (filename has no space).
 * PROPOSED SOURCE ONLY: never executed on host or device.
 * Compile/link as arm64 iPhoneOS with real generated GnuTLS 3.8.9 headers
 * and real iOS archives. No Wine config.h or feature overlay is included.
 * Link with -Wl,-undefined,error -Wl,-no_adhoc_codesign; verify arm64 iOS,
 * exact deployment minimum 17.0, and absence of LC_CODE_SIGNATURE.
 * All 106 are demanded by this control, including Wine-optional APIs.
 */
#include <TargetConditionals.h>
#include <stddef.h>
#include <gnutls/gnutls.h>
#include <gnutls/crypto.h>
#include <gnutls/abstract.h>
#include <gnutls/x509.h>
#include <gnutls/pkcs12.h>
#include <gnutls/dtls.h>

#if !defined(__APPLE__) || !defined(__aarch64__) || !defined(__LP64__)
#error "This is an arm64 Apple target-only link probe."
#endif
#if !TARGET_OS_IPHONE || TARGET_OS_SIMULATOR
#error "Use the iPhoneOS device SDK, never macOS or simulator."
#endif
#if !defined(__ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__) || __ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__ < 170000
#error "This control requires iOS 17.0 or later; metadata gate enforces exactly 17.0."
#endif
#if GNUTLS_VERSION_NUMBER != 0x030809 || GNUTLS_VERSION_MAJOR != 3 || GNUTLS_VERSION_MINOR != 8 || GNUTLS_VERSION_PATCH != 9
#error "Use generated target headers for exactly GnuTLS 3.8.9."
#endif

_Static_assert(sizeof(void *) == 8, "Expected arm64 LP64 pointers");
_Static_assert(__builtin_types_compatible_p(__typeof__(&gnutls_global_init), int (*)(void)), "gnutls_global_init signature");
_Static_assert(__builtin_types_compatible_p(__typeof__(&gnutls_cipher_init), int (*)(gnutls_cipher_hd_t *, gnutls_cipher_algorithm_t, const gnutls_datum_t *, const gnutls_datum_t *)), "gnutls_cipher_init signature");
_Static_assert(__builtin_types_compatible_p(__typeof__(&gnutls_mac_get_key_size), size_t (*)(gnutls_mac_algorithm_t)), "gnutls_mac_get_key_size signature");

/* Real-header-derived pointer types preserve declaration checks.
 * Volatile objects read by main retain every symbol reference even at -O2.
 */
/* Wine required. */
static __typeof__(&gnutls_alert_get) volatile api_gnutls_alert_get = &gnutls_alert_get;
/* Wine required. */
static __typeof__(&gnutls_alert_get_name) volatile api_gnutls_alert_get_name = &gnutls_alert_get_name;
/* Wine required. */
static __typeof__(&gnutls_alert_send) volatile api_gnutls_alert_send = &gnutls_alert_send;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_alpn_get_selected_protocol) volatile api_gnutls_alpn_get_selected_protocol = &gnutls_alpn_get_selected_protocol;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_alpn_set_protocols) volatile api_gnutls_alpn_set_protocols = &gnutls_alpn_set_protocols;
/* Wine required. */
static __typeof__(&gnutls_certificate_allocate_credentials) volatile api_gnutls_certificate_allocate_credentials = &gnutls_certificate_allocate_credentials;
/* Wine required. */
static __typeof__(&gnutls_certificate_free_credentials) volatile api_gnutls_certificate_free_credentials = &gnutls_certificate_free_credentials;
/* Wine required. */
static __typeof__(&gnutls_certificate_get_peers) volatile api_gnutls_certificate_get_peers = &gnutls_certificate_get_peers;
/* Wine required. */
static __typeof__(&gnutls_certificate_set_x509_key) volatile api_gnutls_certificate_set_x509_key = &gnutls_certificate_set_x509_key;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_cipher_add_auth) volatile api_gnutls_cipher_add_auth = &gnutls_cipher_add_auth;
/* Wine required. */
static __typeof__(&gnutls_cipher_decrypt2) volatile api_gnutls_cipher_decrypt2 = &gnutls_cipher_decrypt2;
/* Wine required. */
static __typeof__(&gnutls_cipher_deinit) volatile api_gnutls_cipher_deinit = &gnutls_cipher_deinit;
/* Wine required. */
static __typeof__(&gnutls_cipher_encrypt2) volatile api_gnutls_cipher_encrypt2 = &gnutls_cipher_encrypt2;
/* Wine required. */
static __typeof__(&gnutls_cipher_get) volatile api_gnutls_cipher_get = &gnutls_cipher_get;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_cipher_get_block_size) volatile api_gnutls_cipher_get_block_size = &gnutls_cipher_get_block_size;
/* Wine required. */
static __typeof__(&gnutls_cipher_get_key_size) volatile api_gnutls_cipher_get_key_size = &gnutls_cipher_get_key_size;
/* Wine required. */
static __typeof__(&gnutls_cipher_init) volatile api_gnutls_cipher_init = &gnutls_cipher_init;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_cipher_tag) volatile api_gnutls_cipher_tag = &gnutls_cipher_tag;
/* Wine required. */
static __typeof__(&gnutls_credentials_set) volatile api_gnutls_credentials_set = &gnutls_credentials_set;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_decode_rs_value) volatile api_gnutls_decode_rs_value = &gnutls_decode_rs_value;
/* Wine required. */
static __typeof__(&gnutls_deinit) volatile api_gnutls_deinit = &gnutls_deinit;
/* Wine required. */
static __typeof__(&gnutls_dh_params_deinit) volatile api_gnutls_dh_params_deinit = &gnutls_dh_params_deinit;
/* Wine required. */
static __typeof__(&gnutls_dh_params_export_raw) volatile api_gnutls_dh_params_export_raw = &gnutls_dh_params_export_raw;
/* Wine required. */
static __typeof__(&gnutls_dh_params_import_raw) volatile api_gnutls_dh_params_import_raw = &gnutls_dh_params_import_raw;
/* Wine required. */
static __typeof__(&gnutls_dh_params_init) volatile api_gnutls_dh_params_init = &gnutls_dh_params_init;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_dtls_set_mtu) volatile api_gnutls_dtls_set_mtu = &gnutls_dtls_set_mtu;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_dtls_set_timeouts) volatile api_gnutls_dtls_set_timeouts = &gnutls_dtls_set_timeouts;
/* Wine required. */
static __typeof__(&gnutls_global_deinit) volatile api_gnutls_global_deinit = &gnutls_global_deinit;
/* Wine required. */
static __typeof__(&gnutls_global_init) volatile api_gnutls_global_init = &gnutls_global_init;
/* Wine required. */
static __typeof__(&gnutls_global_set_log_function) volatile api_gnutls_global_set_log_function = &gnutls_global_set_log_function;
/* Wine required. */
static __typeof__(&gnutls_global_set_log_level) volatile api_gnutls_global_set_log_level = &gnutls_global_set_log_level;
/* Wine required. */
static __typeof__(&gnutls_handshake) volatile api_gnutls_handshake = &gnutls_handshake;
/* Wine required. */
static __typeof__(&gnutls_init) volatile api_gnutls_init = &gnutls_init;
/* Wine required. */
static __typeof__(&gnutls_kx_get) volatile api_gnutls_kx_get = &gnutls_kx_get;
/* Wine required. */
static __typeof__(&gnutls_mac_get) volatile api_gnutls_mac_get = &gnutls_mac_get;
/* Wine required. */
static __typeof__(&gnutls_mac_get_key_size) volatile api_gnutls_mac_get_key_size = &gnutls_mac_get_key_size;
/* Wine required. */
static __typeof__(&gnutls_perror) volatile api_gnutls_perror = &gnutls_perror;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pk_to_sign) volatile api_gnutls_pk_to_sign = &gnutls_pk_to_sign;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_bag_decrypt) volatile api_gnutls_pkcs12_bag_decrypt = &gnutls_pkcs12_bag_decrypt;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_bag_deinit) volatile api_gnutls_pkcs12_bag_deinit = &gnutls_pkcs12_bag_deinit;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_bag_get_count) volatile api_gnutls_pkcs12_bag_get_count = &gnutls_pkcs12_bag_get_count;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_bag_get_data) volatile api_gnutls_pkcs12_bag_get_data = &gnutls_pkcs12_bag_get_data;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_bag_get_type) volatile api_gnutls_pkcs12_bag_get_type = &gnutls_pkcs12_bag_get_type;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_bag_init) volatile api_gnutls_pkcs12_bag_init = &gnutls_pkcs12_bag_init;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_deinit) volatile api_gnutls_pkcs12_deinit = &gnutls_pkcs12_deinit;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_get_bag) volatile api_gnutls_pkcs12_get_bag = &gnutls_pkcs12_get_bag;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_import) volatile api_gnutls_pkcs12_import = &gnutls_pkcs12_import;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_init) volatile api_gnutls_pkcs12_init = &gnutls_pkcs12_init;
/* Wine required. */
static __typeof__(&gnutls_pkcs12_verify_mac) volatile api_gnutls_pkcs12_verify_mac = &gnutls_pkcs12_verify_mac;
/* Wine required. */
static __typeof__(&gnutls_priority_set_direct) volatile api_gnutls_priority_set_direct = &gnutls_priority_set_direct;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_decrypt_data) volatile api_gnutls_privkey_decrypt_data = &gnutls_privkey_decrypt_data;
/* Wine required. */
static __typeof__(&gnutls_privkey_deinit) volatile api_gnutls_privkey_deinit = &gnutls_privkey_deinit;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_derive_secret) volatile api_gnutls_privkey_derive_secret = &gnutls_privkey_derive_secret;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_export_dh_raw) volatile api_gnutls_privkey_export_dh_raw = &gnutls_privkey_export_dh_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_export_dsa_raw) volatile api_gnutls_privkey_export_dsa_raw = &gnutls_privkey_export_dsa_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_export_ecc_raw) volatile api_gnutls_privkey_export_ecc_raw = &gnutls_privkey_export_ecc_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_export_rsa_raw) volatile api_gnutls_privkey_export_rsa_raw = &gnutls_privkey_export_rsa_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_export_x509) volatile api_gnutls_privkey_export_x509 = &gnutls_privkey_export_x509;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_generate2) volatile api_gnutls_privkey_generate2 = &gnutls_privkey_generate2;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_import_dh_raw) volatile api_gnutls_privkey_import_dh_raw = &gnutls_privkey_import_dh_raw;
/* Wine required. */
static __typeof__(&gnutls_privkey_import_dsa_raw) volatile api_gnutls_privkey_import_dsa_raw = &gnutls_privkey_import_dsa_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_import_ecc_raw) volatile api_gnutls_privkey_import_ecc_raw = &gnutls_privkey_import_ecc_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_import_rsa_raw) volatile api_gnutls_privkey_import_rsa_raw = &gnutls_privkey_import_rsa_raw;
/* Wine required. */
static __typeof__(&gnutls_privkey_init) volatile api_gnutls_privkey_init = &gnutls_privkey_init;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_privkey_set_spki) volatile api_gnutls_privkey_set_spki = &gnutls_privkey_set_spki;
/* Wine required. */
static __typeof__(&gnutls_privkey_sign_hash) volatile api_gnutls_privkey_sign_hash = &gnutls_privkey_sign_hash;
/* Wine required. */
static __typeof__(&gnutls_protocol_get_version) volatile api_gnutls_protocol_get_version = &gnutls_protocol_get_version;
/* Wine required. */
static __typeof__(&gnutls_pubkey_deinit) volatile api_gnutls_pubkey_deinit = &gnutls_pubkey_deinit;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_encrypt_data) volatile api_gnutls_pubkey_encrypt_data = &gnutls_pubkey_encrypt_data;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_export_dh_raw) volatile api_gnutls_pubkey_export_dh_raw = &gnutls_pubkey_export_dh_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_export_dsa_raw) volatile api_gnutls_pubkey_export_dsa_raw = &gnutls_pubkey_export_dsa_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_export_ecc_raw) volatile api_gnutls_pubkey_export_ecc_raw = &gnutls_pubkey_export_ecc_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_export_rsa_raw) volatile api_gnutls_pubkey_export_rsa_raw = &gnutls_pubkey_export_rsa_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_import_dh_raw) volatile api_gnutls_pubkey_import_dh_raw = &gnutls_pubkey_import_dh_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_import_dsa_raw) volatile api_gnutls_pubkey_import_dsa_raw = &gnutls_pubkey_import_dsa_raw;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_import_ecc_raw) volatile api_gnutls_pubkey_import_ecc_raw = &gnutls_pubkey_import_ecc_raw;
/* Wine required. */
static __typeof__(&gnutls_pubkey_import_privkey) volatile api_gnutls_pubkey_import_privkey = &gnutls_pubkey_import_privkey;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_import_rsa_raw) volatile api_gnutls_pubkey_import_rsa_raw = &gnutls_pubkey_import_rsa_raw;
/* Wine required. */
static __typeof__(&gnutls_pubkey_init) volatile api_gnutls_pubkey_init = &gnutls_pubkey_init;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_set_spki) volatile api_gnutls_pubkey_set_spki = &gnutls_pubkey_set_spki;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_pubkey_verify_hash2) volatile api_gnutls_pubkey_verify_hash2 = &gnutls_pubkey_verify_hash2;
/* Wine required. */
static __typeof__(&gnutls_record_get_max_size) volatile api_gnutls_record_get_max_size = &gnutls_record_get_max_size;
/* Wine required. */
static __typeof__(&gnutls_record_recv) volatile api_gnutls_record_recv = &gnutls_record_recv;
/* Wine required. */
static __typeof__(&gnutls_record_send) volatile api_gnutls_record_send = &gnutls_record_send;
/* Wine required. */
static __typeof__(&gnutls_server_name_set) volatile api_gnutls_server_name_set = &gnutls_server_name_set;
/* Wine required. */
static __typeof__(&gnutls_session_channel_binding) volatile api_gnutls_session_channel_binding = &gnutls_session_channel_binding;
/* Wine required. */
static __typeof__(&gnutls_set_default_priority) volatile api_gnutls_set_default_priority = &gnutls_set_default_priority;
/* Wine required. */
static __typeof__(&gnutls_transport_get_ptr) volatile api_gnutls_transport_get_ptr = &gnutls_transport_get_ptr;
/* Wine required. */
static __typeof__(&gnutls_transport_set_errno) volatile api_gnutls_transport_set_errno = &gnutls_transport_set_errno;
/* Wine required. */
static __typeof__(&gnutls_transport_set_ptr) volatile api_gnutls_transport_set_ptr = &gnutls_transport_set_ptr;
/* Wine required. */
static __typeof__(&gnutls_transport_set_pull_function) volatile api_gnutls_transport_set_pull_function = &gnutls_transport_set_pull_function;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_transport_set_pull_timeout_function) volatile api_gnutls_transport_set_pull_timeout_function = &gnutls_transport_set_pull_timeout_function;
/* Wine required. */
static __typeof__(&gnutls_transport_set_push_function) volatile api_gnutls_transport_set_push_function = &gnutls_transport_set_push_function;
/* Wine required. */
static __typeof__(&gnutls_x509_crt_deinit) volatile api_gnutls_x509_crt_deinit = &gnutls_x509_crt_deinit;
/* Wine required. */
static __typeof__(&gnutls_x509_crt_export) volatile api_gnutls_x509_crt_export = &gnutls_x509_crt_export;
/* Wine required. */
static __typeof__(&gnutls_x509_crt_import) volatile api_gnutls_x509_crt_import = &gnutls_x509_crt_import;
/* Wine required. */
static __typeof__(&gnutls_x509_crt_init) volatile api_gnutls_x509_crt_init = &gnutls_x509_crt_init;
/* Wine required. */
static __typeof__(&gnutls_x509_privkey_deinit) volatile api_gnutls_x509_privkey_deinit = &gnutls_x509_privkey_deinit;
/* Wine required. */
static __typeof__(&gnutls_x509_privkey_export_rsa_raw2) volatile api_gnutls_x509_privkey_export_rsa_raw2 = &gnutls_x509_privkey_export_rsa_raw2;
/* Wine required. */
static __typeof__(&gnutls_x509_privkey_get_pk_algorithm2) volatile api_gnutls_x509_privkey_get_pk_algorithm2 = &gnutls_x509_privkey_get_pk_algorithm2;
/* Wine required. */
static __typeof__(&gnutls_x509_privkey_import_pkcs8) volatile api_gnutls_x509_privkey_import_pkcs8 = &gnutls_x509_privkey_import_pkcs8;
/* Wine required. */
static __typeof__(&gnutls_x509_privkey_init) volatile api_gnutls_x509_privkey_init = &gnutls_x509_privkey_init;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_x509_spki_deinit) volatile api_gnutls_x509_spki_deinit = &gnutls_x509_spki_deinit;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_x509_spki_init) volatile api_gnutls_x509_spki_init = &gnutls_x509_spki_init;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_x509_spki_set_rsa_oaep_params) volatile api_gnutls_x509_spki_set_rsa_oaep_params = &gnutls_x509_spki_set_rsa_oaep_params;
/* Wine optional; required by this control. */
static __typeof__(&gnutls_x509_spki_set_rsa_pss_params) volatile api_gnutls_x509_spki_set_rsa_pss_params = &gnutls_x509_spki_set_rsa_pss_params;

/* Link entry only. This executable must NEVER be launched. */
int main(void)
{
    unsigned missing = 0;
    missing += api_gnutls_alert_get == NULL;
    missing += api_gnutls_alert_get_name == NULL;
    missing += api_gnutls_alert_send == NULL;
    missing += api_gnutls_alpn_get_selected_protocol == NULL;
    missing += api_gnutls_alpn_set_protocols == NULL;
    missing += api_gnutls_certificate_allocate_credentials == NULL;
    missing += api_gnutls_certificate_free_credentials == NULL;
    missing += api_gnutls_certificate_get_peers == NULL;
    missing += api_gnutls_certificate_set_x509_key == NULL;
    missing += api_gnutls_cipher_add_auth == NULL;
    missing += api_gnutls_cipher_decrypt2 == NULL;
    missing += api_gnutls_cipher_deinit == NULL;
    missing += api_gnutls_cipher_encrypt2 == NULL;
    missing += api_gnutls_cipher_get == NULL;
    missing += api_gnutls_cipher_get_block_size == NULL;
    missing += api_gnutls_cipher_get_key_size == NULL;
    missing += api_gnutls_cipher_init == NULL;
    missing += api_gnutls_cipher_tag == NULL;
    missing += api_gnutls_credentials_set == NULL;
    missing += api_gnutls_decode_rs_value == NULL;
    missing += api_gnutls_deinit == NULL;
    missing += api_gnutls_dh_params_deinit == NULL;
    missing += api_gnutls_dh_params_export_raw == NULL;
    missing += api_gnutls_dh_params_import_raw == NULL;
    missing += api_gnutls_dh_params_init == NULL;
    missing += api_gnutls_dtls_set_mtu == NULL;
    missing += api_gnutls_dtls_set_timeouts == NULL;
    missing += api_gnutls_global_deinit == NULL;
    missing += api_gnutls_global_init == NULL;
    missing += api_gnutls_global_set_log_function == NULL;
    missing += api_gnutls_global_set_log_level == NULL;
    missing += api_gnutls_handshake == NULL;
    missing += api_gnutls_init == NULL;
    missing += api_gnutls_kx_get == NULL;
    missing += api_gnutls_mac_get == NULL;
    missing += api_gnutls_mac_get_key_size == NULL;
    missing += api_gnutls_perror == NULL;
    missing += api_gnutls_pk_to_sign == NULL;
    missing += api_gnutls_pkcs12_bag_decrypt == NULL;
    missing += api_gnutls_pkcs12_bag_deinit == NULL;
    missing += api_gnutls_pkcs12_bag_get_count == NULL;
    missing += api_gnutls_pkcs12_bag_get_data == NULL;
    missing += api_gnutls_pkcs12_bag_get_type == NULL;
    missing += api_gnutls_pkcs12_bag_init == NULL;
    missing += api_gnutls_pkcs12_deinit == NULL;
    missing += api_gnutls_pkcs12_get_bag == NULL;
    missing += api_gnutls_pkcs12_import == NULL;
    missing += api_gnutls_pkcs12_init == NULL;
    missing += api_gnutls_pkcs12_verify_mac == NULL;
    missing += api_gnutls_priority_set_direct == NULL;
    missing += api_gnutls_privkey_decrypt_data == NULL;
    missing += api_gnutls_privkey_deinit == NULL;
    missing += api_gnutls_privkey_derive_secret == NULL;
    missing += api_gnutls_privkey_export_dh_raw == NULL;
    missing += api_gnutls_privkey_export_dsa_raw == NULL;
    missing += api_gnutls_privkey_export_ecc_raw == NULL;
    missing += api_gnutls_privkey_export_rsa_raw == NULL;
    missing += api_gnutls_privkey_export_x509 == NULL;
    missing += api_gnutls_privkey_generate2 == NULL;
    missing += api_gnutls_privkey_import_dh_raw == NULL;
    missing += api_gnutls_privkey_import_dsa_raw == NULL;
    missing += api_gnutls_privkey_import_ecc_raw == NULL;
    missing += api_gnutls_privkey_import_rsa_raw == NULL;
    missing += api_gnutls_privkey_init == NULL;
    missing += api_gnutls_privkey_set_spki == NULL;
    missing += api_gnutls_privkey_sign_hash == NULL;
    missing += api_gnutls_protocol_get_version == NULL;
    missing += api_gnutls_pubkey_deinit == NULL;
    missing += api_gnutls_pubkey_encrypt_data == NULL;
    missing += api_gnutls_pubkey_export_dh_raw == NULL;
    missing += api_gnutls_pubkey_export_dsa_raw == NULL;
    missing += api_gnutls_pubkey_export_ecc_raw == NULL;
    missing += api_gnutls_pubkey_export_rsa_raw == NULL;
    missing += api_gnutls_pubkey_import_dh_raw == NULL;
    missing += api_gnutls_pubkey_import_dsa_raw == NULL;
    missing += api_gnutls_pubkey_import_ecc_raw == NULL;
    missing += api_gnutls_pubkey_import_privkey == NULL;
    missing += api_gnutls_pubkey_import_rsa_raw == NULL;
    missing += api_gnutls_pubkey_init == NULL;
    missing += api_gnutls_pubkey_set_spki == NULL;
    missing += api_gnutls_pubkey_verify_hash2 == NULL;
    missing += api_gnutls_record_get_max_size == NULL;
    missing += api_gnutls_record_recv == NULL;
    missing += api_gnutls_record_send == NULL;
    missing += api_gnutls_server_name_set == NULL;
    missing += api_gnutls_session_channel_binding == NULL;
    missing += api_gnutls_set_default_priority == NULL;
    missing += api_gnutls_transport_get_ptr == NULL;
    missing += api_gnutls_transport_set_errno == NULL;
    missing += api_gnutls_transport_set_ptr == NULL;
    missing += api_gnutls_transport_set_pull_function == NULL;
    missing += api_gnutls_transport_set_pull_timeout_function == NULL;
    missing += api_gnutls_transport_set_push_function == NULL;
    missing += api_gnutls_x509_crt_deinit == NULL;
    missing += api_gnutls_x509_crt_export == NULL;
    missing += api_gnutls_x509_crt_import == NULL;
    missing += api_gnutls_x509_crt_init == NULL;
    missing += api_gnutls_x509_privkey_deinit == NULL;
    missing += api_gnutls_x509_privkey_export_rsa_raw2 == NULL;
    missing += api_gnutls_x509_privkey_get_pk_algorithm2 == NULL;
    missing += api_gnutls_x509_privkey_import_pkcs8 == NULL;
    missing += api_gnutls_x509_privkey_init == NULL;
    missing += api_gnutls_x509_spki_deinit == NULL;
    missing += api_gnutls_x509_spki_init == NULL;
    missing += api_gnutls_x509_spki_set_rsa_oaep_params == NULL;
    missing += api_gnutls_x509_spki_set_rsa_pss_params == NULL;
    return missing ? 1 : 0;
}
