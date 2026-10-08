from mqtt_alert import (
    connect_mqtt,
    publish_intrusion,
    disconnect_mqtt
)


# Connexion au broker
if connect_mqtt():

    # Simulation d'une intrusion
    publish_intrusion(

        image_path="alerts/intrusion_test.jpg",

        confidence=0.94,

        camera="webcam"
    )

    input(
        "\nAppuyez sur ENTER pour fermer...\n"
    )

    disconnect_mqtt()