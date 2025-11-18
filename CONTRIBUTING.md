# Cómo Contribuir

¡Gracias por tu interés en contribuir a Awesome Lliurex! Toda ayuda es bienvenida.

## ¿Cómo puedo añadir un proyecto?

1.  **Asegúrate de que el proyecto cumple los requisitos:**
    *   Debe ser relevante para el ecosistema Lliurex.
    *   **No debe** pertenecer a la organización oficial de Lliurex en GitHub. Buscamos proyectos de la comunidad.
    *   Debe tener un repositorio de código fuente accesible.

2.  **Edita el `README.md`:**
    *   Busca la categoría más apropiada para tu proyecto.
    *   Añade una nueva entrada siguiendo el formato:
        ```markdown
        * [Nombre del Proyecto](URL del repositorio) - Descripción breve y clara del proyecto.
        ```

3.  **Crea una Pull Request:**
    *   Haz un "fork" del repositorio.
    *   Crea una nueva rama para tus cambios.
    *   Añade tus cambios y haz commit.
    *   Envía una "Pull Request" con una descripción de lo que has añadido.

## Configuración del buscador automático de repositorios

El proyecto incluye un script `find_new_projects.py` que busca automáticamente nuevos repositorios de Lliurex en GitHub y los clasifica. Para que funcione correctamente, necesitas configurar variables de entorno:

1.  **Crea un archivo `.env`** en la raíz del proyecto con el siguiente contenido:
    ```env
    GITHUB_TOKEN=tu_token_de_github_aqui
    GEMINI_API_KEY=tu_clave_de_api_gemini_aqui
    ```

2.  **Obtener un token de GitHub:**
    *   Ve a [https://github.com/settings/tokens](https://github.com/settings/tokens)
    *   Haz clic en "Generate new token"
    *   Selecciona "Fine-grained personal access token" o "Personal access token (classic)"
    *   Para tokens clásicos, asegúrate de seleccionar el scope `public_repo` para acceder a repositorios públicos
    *   Copia el token generado y úsalo en el archivo `.env`
    *   **Importante:** ¡No compartas este token públicamente!

3.  **Obtener una clave de API de Gemini (opcional):**
    *   Ve a [Google AI Studio](https://aistudio.google.com/)
    *   Crea una cuenta o inicia sesión
    *   Genera una clave de API y úsala en el archivo `.env`
    *   Esto se usa para clasificar automáticamente los repositorios en categorías

¡Gracias por ayudar a hacer esta lista más increíble!
