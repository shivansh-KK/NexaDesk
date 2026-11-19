import argparse
import asyncio
import uuid

from app.agent.agent import get_default_provider, run_agent_turn
from app.db.session import SessionLocal
from app.tools.registry import execute_tool


async def main() -> None:
    parser = argparse.ArgumentParser(description="ShopAssist Customer Support CLI")
    parser.add_argument(
        "--provider", choices=["gemini", "ollama", "mock"], default="mock", help="LLM Provider"
    )
    parser.add_argument(
        "--guardrails", choices=["on", "off"], default="on", help="Enable or disable guardrails"
    )
    parser.add_argument(
        "--prompt",
        choices=["v1_baseline", "v2_guarded"],
        default="v2_guarded",
        help="Prompt version",
    )
    parser.add_argument("--session", default=None, help="Custom session ID")
    args = parser.parse_args()

    session_id = args.session or f"cli-{uuid.uuid4().hex[:8]}"
    guardrails_enabled = args.guardrails == "on"
    provider = get_default_provider(args.provider)

    print("=" * 60)
    print("  ShopAssist Customer Support AI Agent (CLI)")
    print(f"  Session ID : {session_id}")
    print(f"  Provider   : {args.provider}")
    print(f"  Guardrails : {'ENABLED' if guardrails_enabled else 'DISABLED'}")
    print(f"  Prompt     : {args.prompt}")
    print("  Type 'exit' or 'quit' to end session.")
    print("=" * 60)

    db = SessionLocal()
    pending_action = None

    try:
        while True:
            if pending_action:
                user_input = input("\n[CONFIRMATION REQUIRED (yes/no)] > ").strip().lower()
                if user_input in ("yes", "y", "confirm"):
                    # Execute confirmed action
                    tool_name = pending_action["tool_name"]
                    tool_args = pending_action["tool_args"]
                    print(f"\n[Executing Confirmed Action: {tool_name}]...")
                    res = execute_tool(tool_name, tool_args, db, session_id=session_id)
                    print(f"\nShopAssist: {res.message}")
                    pending_action = None
                    continue
                elif user_input in ("no", "n", "cancel"):
                    print("\nShopAssist: Action was cancelled. How else may I assist you?")
                    pending_action = None
                    continue

            user_input = input("\nCustomer > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Session closed. Goodbye!")
                break

            result = await run_agent_turn(
                session_id=session_id,
                user_message=user_input,
                db=db,
                provider=provider,
                guardrails_enabled=guardrails_enabled,
                prompt_version=args.prompt,
            )

            # Display tool calls if any were made
            if result.tool_calls:
                for tc in result.tool_calls:
                    print(f"\n  [TOOL CALL] {tc['tool_name']}({tc['arguments']})")
                    print(
                        f"  [TOOL RESULT] ok={tc['result'].get('ok')} | {tc['result'].get('message')}"
                    )

            print(f"\nShopAssist: {result.reply}")

            if result.pending_action:
                pending_action = result.pending_action

            if result.escalated:
                print("\n  [NOTICE: Conversation has been escalated to a human supervisor]")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
