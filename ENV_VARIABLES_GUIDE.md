# Environment Variables Guide

## 1. Azure Active Directory (Frontend Authentication)

These are used if your application allows logging in with Microsoft/Azure accounts.

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **VITE_AZURE_TENANT_ID** | ID of your Azure organization. | **Azure Portal** > search "Microsoft Entra ID" > **Overview** tab > Copy "Tenant ID". |
| **VITE_AZURE_CLIENT_ID** | ID of your specific App. | **Azure Portal** > **App Registrations** > Click your App (e.g., O2AI-Frontend) > **Overview** > Copy "Application (client) ID". |
| **VITE_AZURE_TENANT_MODE** | Login mode. | Set to `multi` (allow any Microsoft account) or `single` (only your organization). Usually **`single`** for enterprise apps. |
| **VITE_API_BASE_URL** | URL of your Backend API. | Use `http://localhost:8000` for local testing. For production, use your deployed domain (e.g., `https://api.myapp.com`). |

## 2. Azure OpenAI (AI / LLM)

Required for the AI features (summarization, extraction).

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **AZURE_OPENAI_API_KEY** | Secret key for access. | **Azure Portal** > search "Azure OpenAI" > Select your resource > **Keys and Endpoint** (left menu) > Copy **Key 1**. |
| **AZURE_OPENAI_ENDPOINT** | URL of your resource. | Same screen as above (**Keys and Endpoint**). Copy the **Endpoint** URL. |
| **OPENAI_API_VERSION** | API version string. | Use **`2024-02-01`** (or check **Model deployments** for the latest supported version). |
| **AZURE_OPENAI_DEPLOYMENT** | Name of your model. | **Azure AI Studio** (from the OpenAI resource overview) > **Deployments** > Copy the **Deployment Name** (e.g., `gpt-4o`). |

## 3. Azure Storage (Files & PDF Storage)

Used to store the fax PDFs.

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **AZURE_STORAGE_ACCOUNT_URL** | URL of storage account. | **Azure Portal** > **Storage Accounts** > Select account > **Endpoints** (left menu) > Copy **Blob Service** URL. |
| **AZURE_STORAGE_CONNECTION_STRING** | Full access string. | **Azure Portal** > **Storage Accounts** > Select account > **Access keys** (left menu) > Copy **Connection string** (Key 1 or 2). |

## 4. Azure Document Intelligence (OCR)

Used to read text from the PDFs.

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **AZURE_DOCUMENT_INTELLIGENCE_KEY** | Secret key for OCR. | **Azure Portal** > search "Document Intelligence" (formerly Form Recognizer) > Select resource > **Keys and Endpoint** > Copy **Key 1**. |
| **AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT** | URL for OCR. | Same screen as above (**Keys and Endpoint**). Copy the **Endpoint** URL. |

## 5. Epic OAuth (Healthcare Integration)

Crucial: These must match exactly what is registered in the Epic App Orchard.

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **EPIC_CLIENT_ID** | Public ID of your app. | **Epic App Orchard** > Your App > Overview. (Existing project value: `8a3e9014...`) |
| **EPIC_CLIENT_SECRET** | Private Secret. | **Epic App Orchard** > Your App > Certificates/Secrets. **Keep this safe!** |
| **EPIC_REDIRECT_URI** | Callback URL. | Must describe your app's location. <br>Local: `http://localhost:5173/callback` <br>Prod: `https://<your-domain>/` <br>**MUST MATCH EXACTLY** in App Orchard. |
| **BASE_URL** | Your public domain. | Your application's domain (e.g., `https://o2ai-fax-automation.centralus.cloudapp.azure.com`). |
| **EPIC_FHIR_PRIVATE_KEY_PATH** | Path to .pem file. | Path to your generated private key file on the server (e.g., `backend/keys/private_key.pem`). |
| **EPIC_FHIR_JWKS_URL** | Public key URL. | Typically: `<BASE_URL>/.well-known/jwks.json`. Use this URL in Epic App Orchard settings. |
| **EPIC_SCOPES** | Permissions. | From Epic Docs. Typical value: `openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create`. |

## 6. Database (PostgreSQL)

Your Azure Cosmos DB for PostgreSQL connection details.

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **PGHOST** | Server Hostname. | **Azure Portal** > **Azure Cosmos DB for PostgreSQL** > Overview > **Coordinator name**. (e.g., `o2aifax...postgres.database.azure.com`) |
| **PGUSER** | Username. | The admin username you created (e.g., `citus`). |
| **PGPASSWORD** | Password. | The password you set when creating the cluster. |
| **PGDATABASE** | Database Name. | `postgres` (default) or `o2ai_fax_automation` (if you created a specific one). |
| **PGPORT** | Port number. | Always **`5432`**. |

## 7. App Administration

Custom settings for your specific application logic.

| Variable | Description | How to Get It |
| :--- | :--- | :--- |
| **ADMINS / ADMIN_EMAILS** | List of Admin users. | **You define this.** Enter a comma-separated list of emails that should have admin access. <br>Example: `admin@example.com,user@example.com` |
| **ASSIGN_ACCESS_EMAILS** | Permission list. | **You define this.** JSON list of emails allowed to assign tasks. <br>Example: `["doctor@hospital.com", "nurse@hospital.com"]` |
