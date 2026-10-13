"""安装脚本"""

from setuptools import find_packages, setup

setup(
    name="dockmaster",
    version="0.2.2",
    packages=find_packages(),
    include_package_data=True,
    license="MIT",
    license_files=["LICENSE", "THIRD_PARTY_NOTICES.md"],
    install_requires=[
        "docker>=7.0.0",
        "typer>=0.9.0",
        "colorlog>=6.7.0",
        "pyyaml>=6.0",
        "rich>=13.4.2",
        "python-dotenv>=1.0.0",
        "questionary>=2.0.0",
        "click>=8.0.0",
        "shellingham>=1.5.0",
        "croniter>=2.0.0",
        "schedule",
        "loguru>=0.7.0",
        "python-daemon>=3.0.1; os_name == 'posix'",
        "requests>=2.31.0"
    ],
    entry_points={
        "console_scripts": [
            "dm=dockmaster.cli:main",
            "dockmaster=dockmaster.cli:main",
        ],
    },
    python_requires=">=3.8",
    author="Kang Chen",
    author_email="chenkangcs@foxmail.com",
    description="Docker项目和容器管理工具",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    keywords="docker, container, management, devops, automation",
    url="https://github.com/queekye/dockmaster",
    project_urls={
        "Bug Tracker": "https://github.com/queekye/dockmaster/issues",
        "Documentation": "https://github.com/queekye/dockmaster/wiki",
        "Source Code": "https://github.com/queekye/dockmaster",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
)
