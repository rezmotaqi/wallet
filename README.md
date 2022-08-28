# Heisenberg Core Documentation
Before run this project on your system please follow these structures:
1- Install docker and docker compose
2- Create docker network: `docker network create public`
3- Make a .env file in the root project (You can compy from the example)

For running in development enviorments follow this command in root directory.

`
``docker-compose up -d``
`

## Useful tools
One of the best tools in this platform is `manage.py`.
Please run this command to see what you can do:
```
python manage.py
```

## Project Information
1- We have a root user that it's a god of the platform and it defines into settings or .env(recommand). you can add role to another users with this user.


### TODO
1- Add acl for admin's endpoints.
2- Remove redis for device heisenberg.
3- Implement websocket structure.
4- Later, change the Mongodb from this version to latest. for vm with not supported avx use this version `mongo:4.4.10-focal`
5- Please put this command for run: `uvicorn app.main:app --workers 5 --loop asyncio --host heisenberg-core`


### Sample Data


### User Interactions in other collections (other than user collection)

1- Skills ==> owner_id, basic_info.first_name, basic_info.last_name, basic_info.avatar, basic_info.headline
2- Notification ==> (id) in requester_id and requested_id, basic_info.first_name, basic_info.last_name, basic_info.avatar, basic_info.headline
3- Friends ==> (id) in requester_id and requested_id, basic_info.first_name, basic_info.last_name, basic_info.avatar, basic_info.headline
4- Experiences ==> owner_id
5- WorkSamples ==> owner_id
6- Certifications ==> owner_id