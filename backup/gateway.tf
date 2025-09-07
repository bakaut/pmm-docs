resource "yandex_api_gateway" "tg_gateway" {
  name      = "tg-webhook-gateway"
  folder_id = var.folder_id

  spec = <<EOF
openapi: 3.0.1
info:
  title: Telegram Webhook API
  version: "1.0.0"

components:
  securitySchemes:
    telegramBotToken:
      type: apiKey
      in: header
      name: X-Telegram-Bot-Api-Secret-Token

paths:
  /:
    post:
      security:
        - telegramBotToken: []
      x-yc-apigateway-authorizer:
        type: header
        name: X-Telegram-Bot-Api-Secret-Token
        secret: ${data.sops_file.common_secrets.data.webhook_secret}
      x-yc-apigateway-integration:
        type: cloud_functions        # <— актуальный тип
        function_id: ${yandex_function.function.id}
        tag: "$latest"
        service_account_id: ${yandex_iam_service_account.function_sa.id}  # если функция приватная
        payload_format_version: "1.0"
EOF
}

# resource "yandex_api_gateway" "tg_gateway_do" {
#   name      = "tg-gateway-do"
#   folder_id = var.folder_id

#   spec = <<EOF
# openapi: 3.0.1
# info:
#   title: Telegram Webhook API
#   version: "1.0.0"

# components:
#   securitySchemes:
#     telegramBotToken:
#       type: apiKey
#       in: header
#       name: X-Telegram-Bot-Api-Secret-Token

# paths:
#   /:
#     post:
#       security:
#         - telegramBotToken: []
#       x-yc-apigateway-authorizer:
#         type: header
#         name: X-Telegram-Bot-Api-Secret-Token
#         secret: ${data.sops_file.common_secrets.data.webhook_secret}
#       x-yc-apigateway-integration:
#         type: cloud_functions        # <— актуальный тип
#         function_id: ${yandex_function.function_doagent.id}
#         tag: "$latest"
#         service_account_id: ${yandex_iam_service_account.function_sa.id}  # если функция приватная
#         payload_format_version: "1.0"
# EOF
# }


# resource "yandex_api_gateway" "bereginyagpt_gateway" {
#   name      = "bereginyagpt-gateway"
#   folder_id = var.folder_id

#   spec = <<EOF
# openapi: 3.0.1
# info:
#   title: GPT plugin API specification
#   version: "1.0.0"

# components:
#   securitySchemes:
#     gptPluginToken:
#       type: apiKey
#       in: header
#       name: X-Custom-Gpt-Api-Secret-Token

# paths:
#   /start_session:
#     post:
#       operationId: start_session
#       summary: Регистрирует начало бесплатной часовой сессии
#       security:
#         - gptPluginToken: []
#       x-yc-apigateway-authorizer:
#         type: header
#         name: X-Custom-Gpt-Api-Secret-Token
#         secret: ${data.sops_file.common_secrets.data.bereginyagpt_secret_token}
#       x-yc-apigateway-integration:
#         type: cloud_functions        # <— актуальный тип
#         function_id: ${yandex_function.function_bereginyagpt.id}
#         tag: "$latest"
#         service_account_id: ${yandex_iam_service_account.function_sa.id}  # если функция приватная
#         payload_format_version: "1.0"
#   /check_session:
#     post:
#       operationId: check_session
#       summary: Проверяет, не вышел ли бесплатный час с момента старта
#       security:
#         - gptPluginToken: []
#       x-yc-apigateway-authorizer:
#         type: header
#         name: X-Custom-Gpt-Api-Secret-Token
#         secret: ${data.sops_file.common_secrets.data.bereginyagpt_secret_token}
#       x-yc-apigateway-integration:
#         type: cloud_functions        # <— актуальный тип
#         function_id: ${yandex_function.function_bereginyagpt.id}
#         tag: "$latest"
#         service_account_id: ${yandex_iam_service_account.function_sa.id}  # если функция приватная
#         payload_format_version: "1.0"
#   /create_payeer_payment:
#     post:
#       operationId: create_payeer_payment
#       summary: Создаёт платёжную ссылку Payeer для продления сессии
#       security:
#         - gptPluginToken: []
#       x-yc-apigateway-authorizer:
#         type: header
#         name: X-Custom-Gpt-Api-Secret-Token
#         secret: ${data.sops_file.common_secrets.data.bereginyagpt_secret_token}
#       x-yc-apigateway-integration:
#         type: cloud_functions        # <— актуальный тип
#         function_id: ${yandex_function.function_bereginyagpt.id}
#         tag: "$latest"
#         service_account_id: ${yandex_iam_service_account.function_sa.id}  # если функция приватная
#         payload_format_version: "1.0"
#   /check_payeer_payment:
#     post:
#       operationId: check_payeer_payment
#       summary: Проверяет статус платежа Payeer по payment_id
#       security:
#         - gptPluginToken: []
#       x-yc-apigateway-authorizer:
#         type: header
#         name: X-Custom-Gpt-Api-Secret-Token
#         secret: ${data.sops_file.common_secrets.data.bereginyagpt_secret_token}
#       x-yc-apigateway-integration:
#         type: cloud_functions        # <— актуальный тип
#         function_id: ${yandex_function.function_bereginyagpt.id}
#         tag: "$latest"
#         service_account_id: ${yandex_iam_service_account.function_sa.id}  # если функция приватная
#         payload_format_version: "1.0"
# EOF
# }
