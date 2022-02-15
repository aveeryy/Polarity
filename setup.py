from setuptools import setup

if __name__ == "__main__":
    setup(
        include_package_data=True,
        entry_points={"console_scripts": ["polarity = polarity.__main__:main"]},
    )
