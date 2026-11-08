# Chorus: autenticación real con osap-auth

## Contrato comprobado

La lectura del código actual de AI_GAMEPC2 y AI_osap-auth confirma:

- La cuenta y las contraseñas pertenecen exclusivamente a osap-auth.
- POST /auth/login acepta email, password y, opcionalmente, audience.
- POST /auth/refresh acepta refresh_token y la misma audience; rota el refresh y detecta su reutilización.
- Los access tokens son JWT RS256; claims obligatorios iss, sub, aud, exp, iat, jti, con token_use=user.
- JWKS está publicado en /auth/.well-known/jwks.json.
- GET /auth/me ofrece perfil bajo demanda; no se necesita para resolver la propiedad de datos.
- El frontend OSAP actual también tiene un flujo OIDC PKCE mediado por osap-api, pero ese flujo emite tokens con audiencia osap-api. Chorus no debe aceptar esos tokens como si fueran suyos.

## Decisión de Chorus

Chorus es otro servicio con API propia. Su backend hace de cliente de la API de identidad:

1. El navegador envía email y contraseña únicamente al endpoint HTTPS de Chorus.
2. Chorus reenvía la petición a osap-auth /auth/login, fijando en servidor audience=chorus-api.
3. El access token se devuelve al cliente para las peticiones Bearer; el refresh token se guarda en cookie HttpOnly, Secure, SameSite=Lax, limitada a /api/v1/auth.
4. Chorus valida localmente firma RS256, issuer, audience, expiración, jti y token_use=user con JWKS.
5. Refresh se realiza desde el backend y rota la cookie. Logout revoca la sesión actual en osap-auth.

La audiencia no la elige el navegador. Antes de activar login en el despliegue, el administrador de osap-auth debe añadir chorus-api a allowed_token_audiences. Si no está permitida, login/refresh fallan cerrados. No se acepta un token aud=osap-api.

## Por qué no se reutiliza el login OIDC actual de osap-api

El flujo OIDC PKCE de AI_GAMEPC2 está registrado para el cliente osap-api y la emisión de tokens OIDC actual utiliza la audiencia global osap-api. No es correcto reutilizarlo como credencial de Chorus. La API de osap-auth ya permite emitir tokens para una audiencia adicional explícitamente autorizada en /auth/login y /auth/refresh; este piloto utiliza esa capacidad desde el backend, sin almacenar contraseñas ni crear cuentas en Chorus.

Si se quiere ofrecer también login social mediante la pantalla OIDC alojada de osap-auth, habrá que ampliar el registro de RP y la emisión de audiencia por cliente en osap-auth. Ese cambio queda fuera de este repositorio y no se ha realizado.

## Configuración

Copiar osap.toml.example a osap.toml y establecer las URLs reales. Confirmar el issuer y JWKS del entorno desplegado; no asumir que el issuer del ejemplo coincide con producción. No versionar secretos.
