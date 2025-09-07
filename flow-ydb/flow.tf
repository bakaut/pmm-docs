

locals {
  user_hash_flow = data.archive_file.flow_zip.output_md5
}

# Archive the function code once
data "archive_file" "flow_zip" {
  type        = "zip"
  source_dir  = "${path.module}/flow"
  output_path = "${path.module}/flow.zip"
}

resource "yandex_function" "function_flow" {

  name               = "flow"
  description        = "Cloud function for debug PoyMoyMiraFlowBot"
  user_hash          = local.user_hash_flow
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
    ai_models_fallback   = jsonencode(var.ai_models_fallback)
    session_lifetime     = var.session_lifetime
    bot_token            = data.sops_file.common_secrets.data.flow_bot_token
    operouter_key        = data.sops_file.common_secrets.data.flow_operouter_key
    openai_key           = data.sops_file.common_secrets.data.openai_key_poymoymir_moderation
    proxy_url            = data.sops_file.common_secrets.data.proxy_url
    database_url         = data.sops_file.common_secrets.data.database_url_nelyskazka
    ydb_endpoint         = yandex_ydb_database_serverless.cache_db_dev[0].ydb_full_endpoint
    ydb_database         = yandex_ydb_database_serverless.cache_db_dev[0].database_path
    ydb_cache_table      = yandex_ydb_table.cache_table_dev[0].path
    ydb_cache_enabled    = var.ydb_cache_enabled
  }
  content {
    zip_filename = "flow.zip"
  }

  log_options {
    log_group_id = yandex_logging_group.function_logs_flow.id
    min_level    = "LEVEL_UNSPECIFIED"
  }
  depends_on = [yandex_resourcemanager_folder_iam_member.trigger_permission, yandex_storage_bucket.function_bucket, yandex_function.functions, yandex_ydb_database_serverless.cache_db_dev]
}
