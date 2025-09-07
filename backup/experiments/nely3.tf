

locals {
  user_hash_nely3 = data.archive_file.nely3_zip.output_md5
}

# Archive the function code once
data "archive_file" "nely3_zip" {
  type        = "zip"
  source_dir  = "${path.module}/nely3"
  output_path = "${path.module}/nely3.zip"
}

resource "yandex_function" "function_nely3" {

  name               = "nely3"
  description        = "Cloud function Интуиция GutFeelBot"
  user_hash          = local.user_hash_nely3
  entrypoint         = "index.handler"
  runtime            = var.function_runtime
  memory             = var.function_memory
  execution_timeout  = var.function_timeout
  service_account_id = yandex_iam_service_account.function_sa.id

  environment = {
    connect_timeout      = var.connect_timeout
    read_timeout         = var.read_timeout
    retry_total          = var.retry_total
    retry_backoff_factor = var.retry_backoff_factor
    ai_endpoint          = var.ai_endpoint
    ai_model             = var.ai_model
    session_lifetime     = var.session_lifetime
    bot_token            = data.sops_file.common_secrets.data.nely3_bot_token
    supabase_url         = data.sops_file.common_secrets.data.nely_supabase_url
    supabase_key         = data.sops_file.common_secrets.data.nely_supabase_service_key
    operouter_key        = data.sops_file.common_secrets.data.nely_operouter_key
  }
  content {
    zip_filename = "nely3.zip"
  }

  log_options {
    log_group_id = yandex_logging_group.function_logs_nely.id
    min_level    = var.logging_level
  }
  depends_on = [yandex_resourcemanager_folder_iam_member.trigger_permission, yandex_storage_bucket.function_bucket, yandex_function.functions]
}
