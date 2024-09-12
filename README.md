# xipeai-frontend
## Requirements
1. Python
2. Any IDE (preferably VS Code)
## Project setup
### Git Flow (OPTIONAL)
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
4. For step 3., make sure you check the torch and torchvision version/installation you need to use such that it is compatible with your device and the nnUnet framework

## Usage instructions
1. Activate .venv
2. Within the .venv, you need to specify the environment variables for your model, see -> https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/set_environment_variables.md
3. start the flask app by running 'python src/app.py'
4. ![image](https://github.com/user-attachments/assets/b7044d44-e7f8-495a-80cc-85221edfe709) click on the localhost link to get to the webapp


