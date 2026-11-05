pid_file = "/tmp/vault-agent.pid"
vault { address = "http://vault:8200" }
auto_auth {
  method "approle" {
    config = {
      role_id_file_path = "/run/secrets/role_id"
      secret_id_file_path = "/run/secrets/secret_id"
      remove_secret_id_file_after_reading = false
    }
  }
}
template_config {
  static_secret_render_interval = "10s"
  exit_on_retry_failure = false
}
template {
  contents = "{{- with secret \"secret/data/atlasops\" -}}{{ .Data.data.api_key }}{{- end -}}"
  destination = "/run/atlasops/api-key"
  perms = "0640"
  error_on_missing_key = true
}
