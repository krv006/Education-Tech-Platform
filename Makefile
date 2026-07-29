# EdTech — server buyruqlari (docker compose prod).
# Ishlatish: make <target>   (masalan: make fake)
COMPOSE = docker compose -f docker-compose.prod.yml

.PHONY: help deploy remote up down build logs ps fake superuser migrate shell dbshell

help:  ## Buyruqlar ro'yxati
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

deploy:  ## To'liq deploy: nginx stop, .env, build, up (serverda ishlatiladi)
	bash scripts/deploy.sh

remote:  ## Lokal kompyuterdan serverga deploy (ssh: pull + build + up)
	bash scripts/deploy-remote.sh

up:  ## Stack'ni ko'tarish (build bilan)
	$(COMPOSE) up -d --build

down:  ## Stack'ni to'xtatish
	$(COMPOSE) down

logs:  ## Barcha loglarni kuzatish
	$(COMPOSE) logs -f

ps:  ## Servislar holati
	$(COMPOSE) ps

fake:  ## Fake data: teacher / perents / student (parol: 1)
	$(COMPOSE) exec backend sh -c "python manage.py migrate --noinput && python manage.py seed_fake"

superuser:  ## Django admin superuser yaratish
	$(COMPOSE) exec backend python manage.py createsuperuser

migrate:  ## Migratsiyalarni qo'lda ishga tushirish
	$(COMPOSE) exec backend python manage.py migrate

shell:  ## Django shell (backend konteyner ichida)
	$(COMPOSE) exec backend python manage.py shell

dbshell:  ## Postgres psql shell
	$(COMPOSE) exec db psql -U edtech -d edtech
