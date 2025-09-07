

locals {
  user_hash_doagent = data.archive_file.doagent_zip.output_md5
}

# Archive the function code once
data "archive_file" "doagent_zip" {
  type        = "zip"
  source_dir  = "${path.module}/doagent"
  output_path = "${path.module}/doagent.zip"
}

resource "yandex_function" "function_doagent" {

  name               = "doagent"
  description        = "Cloud function for debug PoyMoyMiraDagentBot"
  user_hash          = local.user_hash_doagent
  entrypoint         = "index.handler"
  runtime            = var.function_runtime
  memory             = var.function_memory
  execution_timeout  = var.function_timeout
  service_account_id = yandex_iam_service_account.function_sa.id

  environment = {
    DO_TG_TOKEN       = data.sops_file.common_secrets.data.do_tg_token
    DO_AGENT_ENDPOINT = data.sops_file.common_secrets.data.do_agent_endpoint
    DO_AGENT_KEY      = data.sops_file.common_secrets.data.do_agent_key


  }
  content {
    zip_filename = "doagent.zip"
  }

  log_options {
    log_group_id = yandex_logging_group.function_logs_flow.id
    min_level    = "LEVEL_UNSPECIFIED"
  }
  depends_on = [yandex_resourcemanager_folder_iam_member.trigger_permission, yandex_storage_bucket.function_bucket, yandex_function.functions]
}
