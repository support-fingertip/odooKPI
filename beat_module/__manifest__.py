{
    'name': 'Beat Module',
    'version': '1.1.0',
    'summary': 'Beat tracking with auto sequence, customer and employee link',
    'author': '',
    'depends': ['base', 'contacts', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/beat_views.xml',
        'views/beat_analytics_views.xml',
    ],
    'installable': True,
    'application': True,
}