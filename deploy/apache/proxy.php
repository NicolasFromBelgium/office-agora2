<?php
/**
 * Reverse proxy: /office/* → Office Agora on 127.0.0.1:8088
 * Used until Apache ProxyPass can be enabled with sudo.
 *
 * PHP consumes multipart bodies into $_POST / $_FILES, so php://input is
 * empty for file uploads. Rebuild the multipart request or FastAPI never
 * sees the `file` field.
 */
declare(strict_types=1);

function agora_proxy_sanitize(string $value): string
{
    return str_replace(["\r", "\n"], '', $value);
}

/**
 * @return iterable<array{0:string,1:string,2:string,3:string,4:int}>
 */
function agora_proxy_iter_files(array $files): iterable
{
    foreach ($files as $field => $info) {
        if (!is_array($info) || !array_key_exists('name', $info)) {
            continue;
        }
        if (!is_array($info['name'])) {
            yield [
                (string) $field,
                (string) ($info['name'] ?? ''),
                (string) ($info['type'] ?? ''),
                (string) ($info['tmp_name'] ?? ''),
                (int) ($info['error'] ?? UPLOAD_ERR_NO_FILE),
            ];
            continue;
        }
        foreach ($info['name'] as $idx => $name) {
            yield [
                (string) $field,
                (string) $name,
                (string) ($info['type'][$idx] ?? ''),
                (string) ($info['tmp_name'][$idx] ?? ''),
                (int) ($info['error'][$idx] ?? UPLOAD_ERR_NO_FILE),
            ];
        }
    }
}

function agora_proxy_first_upload_error(array $files): ?string
{
    foreach (agora_proxy_iter_files($files) as [, , , , $error]) {
        if ($error === UPLOAD_ERR_OK || $error === UPLOAD_ERR_NO_FILE) {
            continue;
        }
        if (in_array($error, [UPLOAD_ERR_INI_SIZE, UPLOAD_ERR_FORM_SIZE], true)) {
            return 'Fichier trop volumineux pour le serveur (limite PHP).';
        }
        return 'Échec de l’envoi du fichier.';
    }
    return null;
}

function agora_proxy_build_multipart(array $post, array $files, string $boundary): string
{
    $body = '';
    $addField = null;
    $addField = function (string $name, mixed $value) use (&$body, $boundary, &$addField): void {
        if (is_array($value)) {
            foreach ($value as $key => $item) {
                $addField($name . '[' . $key . ']', $item);
            }
            return;
        }
        $body .= '--' . $boundary . "\r\n";
        $body .= 'Content-Disposition: form-data; name="' . agora_proxy_sanitize($name) . "\"\r\n\r\n";
        $body .= (string) $value . "\r\n";
    };
    foreach ($post as $name => $value) {
        $addField((string) $name, $value);
    }
    foreach (agora_proxy_iter_files($files) as [$name, $filename, $type, $tmp, $error]) {
        if ($error !== UPLOAD_ERR_OK || $tmp === '' || !is_readable($tmp)) {
            continue;
        }
        $filename = agora_proxy_sanitize($filename);
        $type = agora_proxy_sanitize($type !== '' ? $type : 'application/octet-stream');
        $contents = file_get_contents($tmp);
        if ($contents === false) {
            continue;
        }
        $body .= '--' . $boundary . "\r\n";
        $body .= 'Content-Disposition: form-data; name="' . agora_proxy_sanitize($name)
            . '"; filename="' . $filename . "\"\r\n";
        $body .= 'Content-Type: ' . $type . "\r\n\r\n";
        $body .= $contents . "\r\n";
    }
    $body .= '--' . $boundary . "--\r\n";
    return $body;
}

if (defined('AGORA_PROXY_LIB')) {
    return;
}

$backend = 'http://127.0.0.1:8088';
$prefix = '/office';

$uri = $_SERVER['REQUEST_URI'] ?? '/';
$path = parse_url($uri, PHP_URL_PATH) ?: '/';
if ($path === '' || $path === false) {
    $path = $prefix . '/';
}
if ($path === $prefix) {
    $path = $prefix . '/';
}
$query = $_SERVER['QUERY_STRING'] ?? '';
$url = $backend . $path . ($query !== '' ? ('?' . $query) : '');

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$raw = file_get_contents('php://input');
$body = ($raw === false) ? '' : $raw;
$forcedType = null;

$uploadError = agora_proxy_first_upload_error($_FILES);
if ($uploadError !== null) {
    http_response_code(413);
    header('Content-Type: text/plain; charset=utf-8');
    echo $uploadError . "\n";
    exit;
}

if (!empty($_FILES)) {
    $boundary = '----AgoraProxy' . bin2hex(random_bytes(16));
    $body = agora_proxy_build_multipart($_POST, $_FILES, $boundary);
    $forcedType = 'multipart/form-data; boundary=' . $boundary;
} elseif ($body === '' && $method !== 'GET' && $method !== 'HEAD' && !empty($_POST)) {
    $body = http_build_query($_POST);
    $forcedType = 'application/x-www-form-urlencoded';
} elseif (
    $body === ''
    && $method !== 'GET'
    && $method !== 'HEAD'
    && empty($_POST)
    && empty($_FILES)
    && (int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 0
    && str_contains(strtolower((string) ($_SERVER['CONTENT_TYPE'] ?? '')), 'multipart/form-data')
) {
    http_response_code(413);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Fichier trop volumineux (limite PHP).\n";
    exit;
}

$skipRequestHeaders = ['host', 'content-length', 'connection', 'expect'];
if ($forcedType !== null) {
    $skipRequestHeaders[] = 'content-type';
}

$headerLines = [];
foreach (function_exists('getallheaders') ? getallheaders() : [] as $name => $value) {
    $lower = strtolower((string) $name);
    if (in_array($lower, $skipRequestHeaders, true)) {
        continue;
    }
    $headerLines[] = $name . ': ' . $value;
}
if ($forcedType !== null) {
    $headerLines[] = 'Content-Type: ' . $forcedType;
}
if ($body !== '') {
    $headerLines[] = 'Content-Length: ' . (string) strlen($body);
}
$headerLines[] = 'X-Forwarded-Prefix: ' . $prefix;
if (!empty($_SERVER['REMOTE_ADDR'])) {
    $headerLines[] = 'X-Forwarded-For: ' . $_SERVER['REMOTE_ADDR'];
}
$proto = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
$headerLines[] = 'X-Forwarded-Proto: ' . $proto;
if (!empty($_SERVER['HTTP_HOST'])) {
    $headerLines[] = 'X-Forwarded-Host: ' . $_SERVER['HTTP_HOST'];
}

$context = stream_context_create([
    'http' => [
        'method' => $method,
        'header' => implode("\r\n", $headerLines),
        'content' => $body,
        'ignore_errors' => true,
        'follow_location' => 0,
        'timeout' => 60,
    ],
]);

$result = @file_get_contents($url, false, $context);
$headers = $http_response_header ?? [];
if ($result === false && empty($headers)) {
    http_response_code(502);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Office Agora n’est pas joignable (127.0.0.1:8088).\n";
    exit;
}

$status = 502;
if (isset($headers[0]) && preg_match('#HTTP/\S+\s+(\d+)#', $headers[0], $m)) {
    $status = (int) $m[1];
}
http_response_code($status);

$skip = ['transfer-encoding', 'connection', 'keep-alive', 'content-encoding'];
foreach (array_slice($headers, 1) as $line) {
    if (!str_contains($line, ':')) {
        continue;
    }
    [$name, $value] = explode(':', $line, 2);
    if (in_array(strtolower(trim($name)), $skip, true)) {
        continue;
    }
    header(trim($name) . ': ' . trim($value), false);
}

echo $result === false ? '' : $result;
