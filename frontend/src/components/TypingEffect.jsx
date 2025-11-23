import { useState, useEffect } from "react";

export default function TypingEffect({
    texts = [],
    typingSpeed = 50,
    deletingSpeed = 30,
    pause = 1200,
    loop = true,
    className = "typing",
    onComplete = () => {}
}) {
    const [index, setIndex] = useState(0);
    const [pos, setPos] = useState(0);
    const [forward, setForward] = useState(true);
    const [display, setDisplay] = useState("");
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (isPaused) return;
        const current = texts[index];

        let timeout;

        if (forward) {
            timeout = setTimeout(() => {
                const next = current.slice(0, pos + 1);
                setDisplay(next);
                setPos(pos + 1);

                if (next.length === current.length) {
                    setIsPaused(true)
                    setTimeout(() => {
                        setForward(false);
                        setIsPaused(false);
                        if (!loop && index === texts.length - 1) onComplete();
                    }, pause);
                }
            }, typingSpeed);
        } else {
            timeout = setTimeout(() => {
                const next = current.slice(0, pos - 1);
                setDisplay(next);
                setPos(pos - 1);

                if (next.length === 0) {
                    setForward(true);
                    setIndex((index + 1) % texts.length);
                }
            }, deletingSpeed);
        }


        return () => clearTimeout(timeout);
    }, [pos, forward, index, texts, typingSpeed, deletingSpeed, pause, loop, onComplete, isPaused]);

    return (
        <span className={className}>
            {display}
            <span className="cursor">|</span>
        </span>
    );
}