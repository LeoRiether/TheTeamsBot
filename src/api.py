from google.cloud import firestore
import google.cloud.exceptions

def create_team(name, people):
    db = firestore.Client()
    db.collection(u'teams').add({
        'name': name,
        'people': people
    })    

def api_post(req):
    """
    api_post receives a POST request from the Telegram webhook
    and responds accordingly
    """

    data = req.get_json()
    
    

