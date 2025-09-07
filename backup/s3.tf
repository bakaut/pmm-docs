resource "yandex_storage_bucket" "function_bucket" {
  folder_id = var.folder_id
  bucket    = "ycf-storage-${var.function_name}"
  acl       = "private"
}

resource "yandex_storage_bucket" "songs_bucket" {
  folder_id = var.folder_id
  bucket    = var.function_name
  acl       = "public-read"
}
