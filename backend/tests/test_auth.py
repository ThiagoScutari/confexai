def test_login_com_credenciais_validas_retorna_token(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@confexai.local",
        "password": "admin123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()["data"]


def test_login_com_senha_errada_retorna_401(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@confexai.local",
        "password": "senhaerrada"
    })
    assert response.status_code == 401


def test_login_com_email_errado_retorna_401(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "outro@email.com",
        "password": "admin123"
    })
    assert response.status_code == 401
