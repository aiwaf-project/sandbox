FROM php:8.4-cli

WORKDIR /workspace
COPY . /workspace

RUN apt-get update \
  && apt-get install -y --no-install-recommends git unzip libzip-dev default-mysql-client \
  && docker-php-ext-install zip pdo_mysql \
  && pecl install redis apcu \
  && docker-php-ext-enable redis apcu \
  && rm -rf /var/lib/apt/lists/*

RUN echo "apc.enable_cli=1" > /usr/local/etc/php/conf.d/apcu-cli.ini

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
RUN cd /workspace/examples && composer install --no-interaction --prefer-dist --no-progress

CMD ["./vendor/bin/phpunit", "--colors=never", "--do-not-cache-result", "--filter", "TestAdaptersParity|TestAdapterIntegration"]
