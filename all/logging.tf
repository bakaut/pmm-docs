# Create a Logging Group
resource "yandex_logging_group" "function_logs" {
  name             = "${var.function_name}-logs"
  description      = "Logging group for ${var.function_name}"
  retention_period = var.logging_retention_period
}

resource "yandex_logging_group" "function_logs_nely" {
  name             = "nely-logs"
  description      = "Logging group for nely"
  retention_period = var.logging_retention_period
}

resource "yandex_logging_group" "function_logs_flow" {
  name             = "flow-logs"
  description      = "Logging group for flow"
  retention_period = var.logging_retention_period
}

# resource "yandex_logging_group" "function_logs_bereginya" {
#   name             = "bereginya-logs"
#   description      = "Logging group for bereginya"
#   retention_period = var.logging_retention_period
# }


# resource "yandex_logging_group" "function_logs_bereginyagpt" {
#   name             = "bereginya-logs-gpt"
#   description      = "Logging group for bereginyagpt"
#   retention_period = var.logging_retention_period
# }
