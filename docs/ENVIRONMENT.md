# Development environment

Use Python 3.12, Node.js 22, Git, and VS Code with the Python and Pylance extensions.
The project has been checked locally with Python 3.12.5 and Node.js 22.14.0 on Windows.

Open the project root in VS Code. Create the environment with `py -3.12 -m venv .venv`, then follow the install and run commands in README.md. Select `.venv\Scripts\python.exe` using Python: Select Interpreter.

Use `npm.cmd` in PowerShell if the execution policy blocks `npm.ps1`.
If Windows Controlled Folder Access prevents build tools from writing files, use an ordinary development folder where writes are allowed. Do not disable security protection to run this project.

Local environment files, virtual environments, installed dependencies, and build output are excluded from Git. Store machine-specific notes outside the public repository.

Automated checks are documented in README.md. Supabase setup and deployment instructions are in CONNECT_SERVICES.md.

Keep the operating system clock synchronized. If it is behind the authentication provider, freshly issued tokens can fail the issued-at timestamp check until the clock catches up. On Windows, use Settings > Time & language > Date & time > Sync now. Do not disable token timestamp validation to compensate for an incorrect clock.
