from setuptools import setup, find_packages

setup(
    name="queuectl",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "requests",
        "flask",
        "flask-sqlalchemy",
        "pymysql"
    ],
    entry_points={
        "console_scripts": [
            "queuectl = queuectl.queuectl:queuectl",
        ],
    },
)
