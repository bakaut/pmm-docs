

locals {
  user_hash_bereginyagpt = data.archive_file.bereginyagpt_zip.output_md5
}

# Archive the function code once
data "archive_file" "bereginyagpt_zip" {
  type        = "zip"
  source_dir  = "${path.module}/bereginyagpt"
  output_path = "${path.module}/bereginyagpt.zip"
}

resource "yandex_function" "function_bereginyagpt" {

  name               = "bereginyagpt"
  description        = "Cloud function Берегиня GPT store plugin"
  user_hash          = local.user_hash_bereginyagpt
  entrypoint         = "index.handler"
  runtime            = var.function_runtime
  memory             = var.function_memory
  execution_timeout  = var.function_timeout
  service_account_id = yandex_iam_service_account.function_sa.id

  environment = {
    SUPABASE_URL          = data.sops_file.common_secrets.data.nely_supabase_url
    SUPABASE_KEY          = data.sops_file.common_secrets.data.nely_supabase_service_key
    PAYEER_ACCOUNT        = data.sops_file.common_secrets.data.payeer_shop_id
    PAYEER_SECRET         = data.sops_file.common_secrets.data.payeer_secret_key
    PAYEER_ENCRYPTION_KEY = data.sops_file.common_secrets.data.payeer_encryption_key
    CALLBACK_URL          = data.sops_file.common_secrets.data.payeer_callback_url
  }
  content {
    zip_filename = "bereginyagpt.zip"
  }

  log_options {
    log_group_id = yandex_logging_group.function_logs_bereginyagpt.id
    min_level    = var.logging_level_bereginyagpt
  }
  depends_on = [yandex_resourcemanager_folder_iam_member.trigger_permission, yandex_storage_bucket.function_bucket, yandex_function.functions]
}
