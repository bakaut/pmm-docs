
locals {
  user_hash_mindscribe = data.archive_file.mindscribe_zip.output_md5
}

# Archive the function code once
data "archive_file" "mindscribe_zip" {
  type        = "zip"
  source_dir  = "${path.module}/mindscribe"
  output_path = "${path.module}/mindscribe.zip"
}

resource "yandex_function" "function_mindscribe" {

  name               = "mindscribe"
  description        = "Cloud function for MindScribe - AI-powered summary and content analysis bot"
  user_hash          = local.user_hash_mindscribe
  entrypoint         = "index.handler"
  runtime            = var.function_runtime
  memory             = 256
  execution_timeout  = var.function_timeout
  service_account_id = yandex_iam_service_account.function_sa.id

  environment = merge(
    local.base_function_environment,
    {
      operouter_key     = data.sops_file.common_secrets.data.mindscribe_operouter_key
      database_url_dev  = data.sops_file.common_secrets.data.database_url_nelyskazka
      database_url_prod = data.sops_file.common_secrets.data.database_url_poymoymir
    }
  )
  content {
    zip_filename = "mindscribe.zip"
  }
  log_options {
    log_group_id = yandex_logging_group.function_logs_mindscribe.id
    min_level    = "LEVEL_UNSPECIFIED"
  }
  depends_on = [yandex_resourcemanager_folder_iam_member.trigger_permission, yandex_storage_bucket.function_bucket]
}
