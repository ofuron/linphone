cmake_minimum_required(VERSION 3.6)

project(liblinphone++ LANGUAGES CXX)

add_compile_options(-Wall -Werror -Wno-deprecated-declarations)
add_definitions(-DTUNNEL_ENABLED=1)
include_directories(include/ ../../)

set(SOURCES
	src/account_creator.cc
	src/address.cc
	src/auth_info.cc
	src/call.cc
	src/call_log.cc
	src/call_params.cc
	src/call_stats.cc
	src/card_dav_context.cc
	src/card_dav_query.cc
	src/card_dav_response.cc
	src/chat_message.cc
	src/chat_room.cc
	src/conference.cc
	src/conference_params.cc
	src/config.cc
	src/content.cc
	src/core.cc
	src/core_v_table.cc
	src/error_info.cc
	src/event.cc
	src/friend.cc
	src/friend_list.cc
	src/nat_policy.cc
	src/object.cc
	src/payload_type.cc
	src/player.cc
	src/presence_activity.cc
	src/presence_model.cc
	src/presence_note.cc
	src/presence_person.cc
	src/presence_service.cc
	src/proxy_config.cc
	src/sip_transports.cc
	src/tunnel.cc
	src/tunnel_config.cc
	src/vcard.cc
	src/vcard_context.cc
	src/video_policy.cc
	src/xml_rpc_request.cc
	src/xml_rpc_session.cc
)

add_library(linphone++ ${SOURCES})

