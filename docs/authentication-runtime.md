# Chorus: autenticación real con osap-auth

## Contrato comprobado

La lectura del código actual de AI_GAMEPC2 y AI_osap-auth confirma:

- La cuenta y las contraseñas pertenecen exclusivamente a osap-auth.
- POST /auth/login acepta email y password y devuelve access_token, refresh_token, user_id, roles y email_verified.
- POST /auth/refresh acepta refresh_token y rota la sesión.
- GET /auth/me exige un access token válido y lo verifica con el emisor y la audiencia predeterminados de osap-auth (aud=osap-api).
- Los access tokens son JWT RS256; contienen iss, sub, aud, exp, iat, jti y token_use=user.
- JWKS está publicado en /auth/.well-known/jwks.json.
- GET /auth/me devuelve el perfil y el estado de onboarding; POST /auth/onboarding registra nickname y aceptación de las versiones legales.
- El frontend OSAP actual dispone además de un flujo OIDC PKCE mediado por osap-api. Su callback está configurado para la SPA OSAP, no para Chorus.

## Decisión de Chorus

Chorus no acepta ni interpreta localmente un JWT de osap-api. Lo utiliza como credencial únicamente para consultar el endpoint de su audiencia prevista: osap-auth /auth/me. Es osap-auth quien valida firma, emisor, audiencia, expiración, estado de cuenta y devuelve el user_id autoritativo.

1. El navegador envía email y contraseña únicamente al endpoint HTTPS de Chorus.
2. Chorus reenvía la petición a osap-auth /auth/login sin cambiar la audiencia predeterminada.
3. El access token se devuelve al cliente para las peticiones Bearer; el refresh token se guarda en cookie HttpOnly, Secure, SameSite=Lax, limitada a /api/v1/auth.
4. En cada operación protegida, Chorus reenvía el Bearer a osap-auth /auth/me. La propiedad de los datos se deriva del user_id devuelto por ese servicio, nunca de un campo del navegador.
5. Si el perfil indica onboarding.required=true, Chorus devuelve 403 ONBOARDING_REQUIRED. La API ofrece endpoints para consultar el perfil/avisos legales y completar el onboarding.
6. Refresh se realiza desde el backend y rota la cookie. Logout revoca la sesión actual en osap-auth.

Este diseño evita reutilizar localmente un token cuya audiencia no es Chorus y no requiere modificar osap-auth. La contrapartida es una consulta de identidad a osap-auth por petición protegida; se podrá introducir una introspección firmada o un cliente OIDC propio cuando el contrato de Auth admita una audiencia por RP.

## Login social y OIDC

La primera entrega del backend Chorus utiliza el endpoint de email/password que existe en osap-auth y que está documentado en el contrato de login de OSAP. No incorpora todavía el login social de Google/GitHub. El flujo OIDC PKCE actual de osap-api está asociado a su callback y a su SPA; no se redirige a Chorus ni se reutiliza su token como si tuviera otra audiencia.

Para ofrecer login social directamente en Chorus habrá que registrar Chorus como RP y ampliar el contrato de emisión/introspección de tokens por cliente en osap-auth. No se ha modificado ese repositorio.

## Configuración

Copiar osap.toml.example a osap.toml y establecer la URL pública real de osap-auth. El backend no necesita acceder a la base de datos de Auth ni guardar contraseñas. No versionar secretos.
