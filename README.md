# xipeai-frontend
## Project setup
### Git Flow
Git Flow is a popular Git branching strategy aimed at simplifying release management. 

1. Install Git Flow
   - **Windows:** Git Flow is included in the Git for Windows distribution
   - **MacOS:** Use Homebrew with 'brew install git-flow-avh'.
   - **Linux:** Use apt or yum depending on your distribution, e.g., 'sudo apt-get install git-flow'.
  
2. Install the Git Flow extension by Sergey Romanov
3. Initialize Git Flow in your repository
   - Navigate to your repository
   - Open the terminal and run 'git flow init'
   - You are asked which names the branches should be assigned, you can press enter until finished
4. For further information how to create branches and merge, ask @Fabio Di Frisco


### Create .venv and install dependencies
A virtual environment in the context of Python development is a self-contained directory that contains a Python installation for a particular version of Python, plus a number of additional packages.

1. Create a virtual environment by running 'python -m venv .venv' in your repository
2. To activate the venv run 'source .venv/bin/activate' (on Linux / macOS) or .venv\Scripts\Activate.ps1 (on Windows)
3. To install all packages run 'pip install -r requirements.txt'

