


3. Дать необходимые права на управление tf state и папками yandex cloud:
   ```bash
   yc resource-manager folder add-access-binding \
   --id b1gfqer34aahm1shkj3m \
   --role resource-manager.admin \
   --service-account-name tf-admin

   yc resource-manager folder add-access-binding \
   --id b1gfqer34aahm1shkj3m \
   --role serverless.functions.admin \
   --service-account-name tf-admin

   yc resource-manager folder add-access-binding \
   --id b1gfqer34aahm1shkj3m \
   --role resource-manager.admin \
   --service-account-name tf-admin


   yc resource-manager folder add-access-binding \
   --id b1gfqer34aahm1shkj3m \
   --role iam.serviceAccounts.admin \
   --service-account-name tf-admin

   yc resource-manager folder add-access-binding \
   --id b1gfqer34aahm1shkj3m \
   --role storage.admin \
   --service-account-name tf-admin

   yc resource-manager folder add-access-binding \
   --id b1gfqer34aahm1shkj3m \
   --role logging.admin \
   --service-account-name tf-admin
   ```

4. Вручную запустить миграции баз supabase:
   ```bash
   poymoymir/init.sql
   poymoymir/migrate-1.sql
   ```

5. Применить terraform:
   ```bash
   terraform init -reconfigure -backend-config="access_key=" -backend-config="secret_key="
   terraform plan
   terraform apply
   ```

6. Зарегистрируйте yandex gateway как telegramm webhook:
   ```bash
   curl -F "url=https://<YOUR_GATEWAY>/" \
        -F "secret_token=$WEBHOOK_SECRET" \
        https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook
   ```
