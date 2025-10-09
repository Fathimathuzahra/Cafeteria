from django.urls import path
from . import views

urlpatterns = [
    # Auth & Landing
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("menu/", views.view_menu, name="menu"),
    
    # Student / User URLs
    path("user/dashboard/", views.user_dashboard, name="user_dashboard"),
    path("user/today-menu/", views.user_menu_list, name="user_menu_list"),
    path("user/cart/", views.cart_view, name="cart_view"),
    path("user/cart/add/<int:item_id>/", views.cart_add, name="cart_add"),  # Updated
    path("user/cart/update/", views.cart_update, name="cart_update"),  # Added
    path("user/cart/remove/<str:key>/", views.cart_remove, name="cart_remove"),  # Updated
    path("user/cart/clear/", views.cart_clear, name="cart_clear"),
    path("user/cart/migrate/", views.migrate_cart, name="cart_migrate"),
    path('checkout/', views.checkout, name='checkout'),
    path("user/tokens/", views.my_tokens, name="my_tokens"),
    path("user/tokens/history/", views.user_tokens, name="user_tokens"),
    path("user/token/<int:token_id>/review/", views.add_review, name="add_review"),
    path("user/notifications/", views.my_notifications, name="my_notifications"),
    path("user/notifications/read/", views.mark_notifications_read, name="mark_notifications_read"),
    path("user/reviews/", views.reviews, name="reviews"),
    path('token/pay-success/<str:code>/', views.mock_payment_success, name='mock_payment_success'),
    # Add to your urlpatterns in urls.py:
    path('payment/process/<str:code>/', views.process_upi_payment, name='process_upi_payment'),
    path('display/now-serving/', views.now_serving_display, name='now_serving_display'),
        # Token URLs
    path('token/code/<str:code>/', views.token_ticket, name='token_ticket'),
    path('token/order/<int:order_id>/', views.fetch_token, name='fetch_token'),
    path("token/cancel/<str:token_code>/", views.cancel_token, name="cancel_token"),

    # Staff URLs
    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/menu/", views.menu_list, name="menu_list"),
    path("staff/view-menu/", views.staff_view_menu, name="staff_view_menu"),
    path("staff/menu/add/", views.add_menu_item, name="menu_create"),
    path("staff/menu/delete/<int:pk>/", views.delete_daily_menu_item, name="menu_delete"),  # Daily menu deletion
    path("staff/menu/delete_main/<int:pk>/", views.delete_main_menu_item, name="main_menu_delete"),  # Main menu deletion
    path("staff/menu/<int:item_id>/update_quantity/", views.update_item_quantity, name="update_item_quantity"),
    path("staff/menu/reset_all_stock/", views.reset_all_stock, name="reset_all_stock"),
    path("staff/menu/edit/<int:pk>/", views.edit_daily_menu_item, name="menu_edit"),  # Daily menu
    path("staff/menu/edit-main/<int:pk>/", views.edit_main_menu_item, name="edit_main_menu_item"),  # Main menu
    path("staff/tokens/", views.tokens_today, name="tokens_today"),
        # QR Code endpoints
    path('api/tokens/<str:token_code>/qr-data/', views.generate_qr_data, name='generate_qr_data'),
    path('token/<str:code>/process-payment/', views.process_upi_payment, name='process_upi_payment'),
    path('token/<str:code>/mock-payment/', views.mock_payment_success, name='mock_payment_success'),
    
    # Webhook for automatic payment confirmation (if you integrate with payment gateway)
    path('api/payment-webhook/', views.PaymentWebhookView.as_view(), name='payment_webhook'),
    # Admin URLs
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/reports/", views.admin_reports, name="admin_reports"),
    path("admin/reviews/", views.admin_reviews, name="admin_reviews"),
    path("admin/today-menu/", views.admin_menu_list, name="admin_menu_list"),  # Fixed typo
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/users/add/', views.admin_add_user, name='admin_add_user'),
    path('admin/users/delete/<int:user_id>/', views.admin_delete_user, name='admin_delete_user'),
    path('admin/menu/view/', views.admin_view_menu, name='admin_view_menu'),
]