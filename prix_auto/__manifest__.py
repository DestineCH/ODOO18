{
    'name': "Prix Automatique Mazout",
    'version': '1.0',
    'summary': "Mise à jour automatique des prix du mazout depuis le SPF Économie",
    'author': "Destine",
    'depends': ['product'],
    'data': [
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}