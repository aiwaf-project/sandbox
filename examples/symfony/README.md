# Symfony Example

## 1. Request bootstrap

Create `src/Security/AiWafBootstrap.php`:

```php
<?php

declare(strict_types=1);

namespace App\Security;

use AIWAF\AIWAF;
use AIWAF\Adapters\InMemoryAdapter;
use AIWAF\RateLimiter;
use Symfony\Component\Routing\RouterInterface;

final class AiWafBootstrap
{
    public static function protect(RouterInterface $router): void
    {
        AIWAF::setPathExistsResolver(static function (string $path) use ($router): bool {
            $candidate = '/' . ltrim((string) strtok($path, '?'), '/');
            foreach ($router->getRouteCollection() as $route) {
                $routePath = (string) $route->getPath();
                if ($routePath !== '' && ($candidate === $routePath || strpos($candidate, rtrim($routePath, '/') . '/') === 0)) {
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

Invoke it early in your kernel/request pipeline.

## 2. Console trainer command

Create `src/Command/TrainAiWafCommand.php`:

```php
<?php

declare(strict_types=1);

namespace App\Command;

use AIWAF\AIWAF;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

#[AsCommand(name: 'aiwaf:train', description: 'Run AIWAF log trainer')]
final class TrainAiWafCommand extends Command
{
    protected function configure(): void
    {
        $this
            ->addOption('force-ai', null, InputOption::VALUE_NONE)
            ->addOption('disable-ai', null, InputOption::VALUE_NONE);
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $waf = new AIWAF();
        $waf->detectAndTrain((bool) $input->getOption('disable-ai'), (bool) $input->getOption('force-ai'));
        $output->writeln('AIWAF training complete: ' . json_encode(AIWAF::getLastTrainingTelemetry()));

        return Command::SUCCESS;
    }
}
```

Then run `php bin/console aiwaf:train`.
