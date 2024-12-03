// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

import { Text } from "@fluentui/react";
import { Info24Regular, Pin24Regular } from "@fluentui/react-icons";
import styles from "./DisastersButton.module.css";

interface Props {
    className?: string;
    onClick: () => void;
}

export const DisastersButton = ({ className, onClick }: Props) => {
    return (
        <div className={`${styles.container} ${className ?? ""}`} onClick={onClick}>
            <Pin24Regular/>
            <Text>{"Change Current Disaster"}</Text>
        </div>
    );
};
