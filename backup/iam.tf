resource "yandex_iam_service_account" "function_sa" {
  name      = "${var.function_name}-${terraform.workspace}-sa"
  folder_id = var.folder_id
}

resource "yandex_resourcemanager_folder_iam_member" "trigger_permission" {
  folder_id = var.folder_id
  role      = "functions.functionInvoker"
  member    = "serviceAccount:${yandex_iam_service_account.function_sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "logger_permission" {
  folder_id = var.folder_id
  role      = "logging.writer"
  member    = "serviceAccount:${yandex_iam_service_account.function_sa.id}"
}

# Grant the service account permissions to access to the buckets
resource "yandex_resourcemanager_folder_iam_member" "function_sa_bucket_admin" {
  folder_id = var.folder_id
  role      = "storage.editor"
  member    = "serviceAccount:${yandex_iam_service_account.function_sa.id}"
}

# Grant the service account permissions to access to YDB
resource "yandex_resourcemanager_folder_iam_member" "function_sa_ydb_admin" {
  folder_id = var.folder_id
  role      = "ydb.editor"
  member    = "serviceAccount:${yandex_iam_service_account.function_sa.id}"
}
