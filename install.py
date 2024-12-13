import launch

if not launch.is_installed("xmltodict"):
    launch.run_pip("install xmltodict", "requests-xmltodict")
    
if not launch.is_installed("furl"):
    launch.run_pip("install furl", "requests-furl")
