import cv2

# On ouvre la caméra USB (index 0)
cap = cv2.VideoCapture(0)

print("Appuyez sur 'q' pour fermer la fenêtre")

while True:
    # On capture l'image frame par frame
    ret, frame = cap.read()
    
    if not ret:
        print("Erreur de réception du flux")
        break

    # On affiche l'image dans une fenêtre nommée 'Live'
    cv2.imshow('Retour Camera USB', frame)

    # Si on appuie sur la touche 'q', on arrête
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# On libère tout
cap.release()
cv2.destroyAllWindows()
