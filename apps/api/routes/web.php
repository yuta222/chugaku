<?php

use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('welcome');
});

Route::get('/admin/{path?}', function (?string $path = null) {
    $adminRoot = public_path('admin');
    $indexFile = $adminRoot.'/index.html';

    abort_unless(File::exists($indexFile), 404);

    if ($path !== null) {
        $candidate = realpath($adminRoot.DIRECTORY_SEPARATOR.$path);
        $resolvedAdminRoot = realpath($adminRoot);

        if (
            $candidate !== false &&
            $resolvedAdminRoot !== false &&
            str_starts_with($candidate, $resolvedAdminRoot.DIRECTORY_SEPARATOR) &&
            is_file($candidate)
        ) {
            return response()->file($candidate);
        }
    }

    return response()->file($indexFile);
})->where('path', '.*');
