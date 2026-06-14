# fix-compose-postgres-naming

Fix docker compose v5.0.2 strict validation: base compose 用 postgres/redis 作 service name,dev compose extends 拉过来 depends_on 引用被 strict validation 当 unresolved. 改 base compose 命名对齐 dev compose (chatbiz-postgres/chatbiz-redis),同步所有 depends_on 引用。
