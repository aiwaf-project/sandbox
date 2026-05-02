# Laravel Example

## 1. Service Provider bootstrap

Create `app/Providers/AiWafServiceProvider.php`:

```php
<?php

declare(strict_types=1);

namespace App\Providers;

use AIWAF\AIWAF;
use AIWAF\Adapters\InMemoryAdapter;
use AIWAF\RateLimiter;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\ServiceProvider;

class AiWafServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        AIWAF::setPathExistsResolver(static function (string $path): bool {
            $candidate = '/' . ltrim((string) strtok($path, '?'), '/');
            foreach (Route::getRoutes() as $route) {
                $uri = '/' . ltrim($route->uri(), '/');
                if ($candidate === $uri || strpos($candidate, $uri . '/') === 0) {
                    return true;
                }
            }
            return false;
        });

        RateLimiter::initAdapter(new InMemoryAdapter());
        AIWAF::protect();
    }
}
```

Register it in `config/app.php` providers list.

## 2. Training command

Create `app/Console/Commands/TrainAiWaf.php`:

```php
<?php

declare(strict_types=1);

namespace App\Console\Commands;

use AIWAF\AIWAF;
use Illuminate\Console\Command;

class TrainAiWaf extends Command
{
    protected $signature = 'aiwaf:train {--force-ai} {--disable-ai}';
    protected $description = 'Run AIWAF log trainer';

    public function handle(): int
    {
        $waf = new AIWAF();
        $waf->detectAndTrain((bool) $this->option('disable-ai'), (bool) $this->option('force-ai'));
        $this->info('AIWAF training complete: ' . json_encode(AIWAF::getLastTrainingTelemetry()));

        return self::SUCCESS;
    }
}
```

Then run `php artisan aiwaf:train`.
