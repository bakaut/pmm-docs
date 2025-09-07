variable "cloud_id" {
  description = "Yandex cloud id"
  type        = string
  default     = "b1gugm80kb7nbfiqt9kj"
}

variable "folder_id" {
  description = "Yandex cloud folder id"
  type        = string
  default     = "b1gfqer34aahm1shkj3m"
}

variable "region_id" {
  description = "Yandex cloud region id"
  type        = string
  default     = "ru-central1"
}

variable "zone" {
  description = "Yandex cloud zone"
  type        = string
  default     = "ru-central1-a"
}
variable "function_name" {
  description = "Name of the cloud function"
  type        = string
  default     = "poymoymir"
}

variable "function_memory" {
  description = "Memory size for the function in Mb"
  type        = number
  default     = 128
}

variable "function_timeout" {
  description = "Function timeout in seconds"
  type        = number
  default     = 240
}

variable "connect_timeout" {
  description = "Request connect timeout in seconds"
  type        = number
  default     = 10
}

variable "read_timeout" {
  description = "Request read timeout in seconds"
  type        = number
  default     = 30
}

variable "function_runtime" {
  description = "Function runtime"
  type        = string
  default     = "python312"
}

variable "retry_total" {
  description = "Total number of retries"
  type        = number
  default     = 3
}

variable "retry_backoff_factor" {
  description = "Backoff factor for retries"
  type        = number
  default     = 2
}

variable "logging_level" {
  description = "Logging level (LEVEL_UNSPECIFIED, TRACE, DEBUG, INFO, WARN, ERROR, FATAL)"
  type        = string
  default     = "ERROR"
}

variable "logging_retention_period" {
  description = "Logging retention period"
  type        = string
  default     = "168h"

}

variable "ai_model" {
  description = "AI model to use (openrouter)"
  type        = string
  default     = "openai/gpt-4o"
}

variable "ai_models_fallback" {
  description = "AI fallback models list to use (openrouter) 3 is maximum"
  type        = list(string)
  default = [
    "openai/gpt-4o",
    "openai/gpt-4o-2024-11-20",
    "openai/gpt-4o-2024-08-06"
  ]
}

variable "ai_endpoint" {
  description = "AI endpoint to use (openrouter)"
  type        = string
  default     = "https://openrouter.ai/api/v1/chat/completions"
}

variable "session_lifetime" {
  description = "Session lifetime in hours"
  type        = number
  default     = 262800 # 30 years
}

variable "function_names" {
  type        = list(string)
  description = "PoyMoyMir function names"
  default = [
    "carefulness",
    "sincerity",
    "live-service"
  ]
}

variable "ydb_cache_enabled" {
  description = "Enable YDB cache"
  type        = bool
  default     = false
}

# variable "logging_level_bereginyagpt" {
#   description = "Logging level (LEVEL_UNSPECIFIED, TRACE, DEBUG, INFO, WARN, ERROR, FATAL)"
#   type        = string
#   default     = "LEVEL_UNSPECIFIED"

# }
