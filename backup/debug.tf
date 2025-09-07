

locals {
  user_hash_debug = data.archive_file.debug_zip.output_md5
}

# Archive the function code once
data "archive_file" "debug_zip" {
  type        = "zip"
  source_dir  = "${path.module}/debug"
  output_path = "${path.module}/debug.zip"
}

resource "yandex_function" "debug" {

  name               = "trace"
  description        = "Cloud function"
  user_hash          = local.user_hash_root
  entrypoint         = "index.handler"
  runtime            = var.function_runtime
  memory             = var.function_memory
  execution_timeout  = var.function_timeout
  service_account_id = yandex_iam_service_account.function_sa.id

  environment = {
    OPENROUTER_KEY = data.sops_file.common_secrets.data.operouter_key
  }
  content {
    zip_filename = "debug.zip"
  }

  log_options {
    log_group_id = yandex_logging_group.function_logs.id
    min_level    = var.logging_level
  }
  depends_on = [yandex_resourcemanager_folder_iam_member.trigger_permission, yandex_storage_bucket.function_bucket, yandex_function.functions]
}
