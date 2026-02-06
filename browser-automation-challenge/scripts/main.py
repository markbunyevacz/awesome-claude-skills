#!/usr/bin/env python3
"""CLI entry point for Browser Challenge Agent."""

import argparse
import os
import sys
import logging

def main():
    parser = argparse.ArgumentParser(
        description="Browser Challenge Agent - Solve 30 challenges in under 5 minutes"
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "anthropic", "openai"],
        default="openrouter",
        help="LLM provider (default: openrouter)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: claude-sonnet-4-20250514 for anthropic, gpt-4o for openai)"
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run with visible browser window (not headless)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Total timeout in seconds (default: 300 = 5 minutes)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="run_stats.json",
        help="Output file for metrics (default: run_stats.json)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose logging (default: True)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Check API key
    if args.provider == "openrouter":
        if not os.environ.get("Openrouter") and not os.environ.get("OPENROUTER_API_KEY"):
            print("ERROR: Openrouter environment variable not set")
            print("Set it with: export Openrouter=your-key-here")
            sys.exit(1)
    elif args.provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ERROR: ANTHROPIC_API_KEY environment variable not set")
            print("Set it with: export ANTHROPIC_API_KEY=your-key-here")
            sys.exit(1)
    elif args.provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            print("ERROR: OPENAI_API_KEY environment variable not set")
            print("Set it with: export OPENAI_API_KEY=your-key-here")
            sys.exit(1)
    
    # Import and run
    from runner import run_challenge
    
    verbose = args.verbose and not args.quiet
    
    print(f"Starting Browser Challenge Agent")
    print(f"Provider: {args.provider}")
    print(f"Model: {args.model or 'default'}")
    print(f"Headless: {not args.visible}")
    print(f"Timeout: {args.timeout}s")
    print(f"Output: {args.output}")
    print()
    
    try:
        metrics = run_challenge(
            provider=args.provider,
            model=args.model,
            headless=not args.visible,
            timeout=args.timeout,
            output_file=args.output,
            verbose=verbose,
        )
        
        # Exit with appropriate code
        if metrics.challenges_completed >= 30:
            print("\nSUCCESS: All 30 challenges completed!")
            sys.exit(0)
        elif metrics.challenges_completed >= 25:
            print(f"\nPARTIAL SUCCESS: {metrics.challenges_completed}/30 challenges completed")
            sys.exit(0)
        else:
            print(f"\nFAILED: Only {metrics.challenges_completed}/30 challenges completed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        logging.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
