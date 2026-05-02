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
