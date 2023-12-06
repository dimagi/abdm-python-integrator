REG_API_URL = "/v1/registration/aadhaar/"
GENERATE_AADHAAR_OTP_URL = REG_API_URL + "generateOtp"
GENERATE_MOBILE_OTP_URL = REG_API_URL + "generateMobileOTP"
VERIFY_AADHAAR_OTP_URL = REG_API_URL + "verifyOTP"
VERIFY_MOBILE_OTP_URL = REG_API_URL + "verifyMobileOTP"
CREATE_HEALTH_ID_URL = REG_API_URL + "createHealthIdWithPreVerified"

AUTH_OTP_URL = "/v1/auth/init"
CONFIRM_WITH_MOBILE_OTP_URL = "/v1/auth/confirmWithMobileOTP"
CONFIRM_WITH_AADHAAR_OTP_URL = "/v1/auth/confirmWithAadhaarOtp"
ACCOUNT_INFORMATION_URL = "/v1/account/profile"
SEARCH_BY_HEALTH_ID_URL = "/v1/search/searchByHealthId"
HEALTH_CARD_PNG_FORMAT = "/v1/account/getPngCard"
EXISTS_BY_HEALTH_ID = "/v1/search/existsByHealthId"
