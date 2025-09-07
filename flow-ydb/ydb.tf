

resource "yandex_ydb_database_serverless" "cache_db_dev" {
  count = var.ydb_cache_enabled ? 1 : 0
  name        = "dev-bot-cache"
  folder_id   = var.folder_id
  location_id = var.region_id
}

resource "yandex_ydb_table" "cache_table_dev" {
  count = var.ydb_cache_enabled ? 1 : 0
  path              = "cachemessages"
  connection_string = yandex_ydb_database_serverless.cache_db_dev[0].ydb_full_endpoint

  ttl {
    column_name     = "created_at"
    expire_interval = "P1D" # 1 день (24 ч) — ISO 8601
  }

  column {
    name = "id"
    type = "Utf8"
  }
  column {
    name = "session_id"
    type = "Utf8"
  }
  column {
    name = "user_id"
    type = "Utf8"
  }
  column {
    name = "role"
    type = "Utf8"
  }
  column {
    name = "content"
    type = "Utf8"
  }
  column {
    name = "created_at"
    type = "datetime"
  }

  primary_key = ["id"]
}
