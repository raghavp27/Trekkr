import React, { useState } from 'react';
import {
    View,
    Text,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    Alert,
    ActivityIndicator,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors } from '@/constants/theme';
import { Ionicons } from '@expo/vector-icons';
import { resetPassword } from '@/services/api';

export default function ResetPasswordScreen() {
    const [token, setToken] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const router = useRouter();
    const colorScheme = useColorScheme();
    const colors = Colors[colorScheme ?? 'light'];

    const validateForm = (): string | null => {
        if (!token.trim() || !password.trim() || !confirmPassword.trim()) {
            return 'Please fill in all fields';
        }

        if (password.length < 8) {
            return 'Password must be at least 8 characters long';
        }

        if (!/[a-z]/.test(password)) {
            return 'Password must contain at least one lowercase letter';
        }

        if (!/[A-Z]/.test(password)) {
            return 'Password must contain at least one uppercase letter';
        }

        if (!/[0-9]/.test(password)) {
            return 'Password must contain at least one number';
        }

        if (password !== confirmPassword) {
            return 'Passwords do not match';
        }

        return null;
    };

    const handleSubmit = async () => {
        const validationError = validateForm();
        if (validationError) {
            Alert.alert('Validation Error', validationError);
            return;
        }

        setIsLoading(true);
        try {
            await resetPassword({
                token: token.trim(),
                new_password: password,
            });
            Alert.alert(
                'Success',
                'Your password has been reset. Please sign in with your new password.',
                [
                    {
                        text: 'Sign In',
                        onPress: () => router.replace('/login'),
                    },
                ]
            );
        } catch (error: any) {
            Alert.alert(
                'Reset Failed',
                error.message || 'Invalid, expired, or already used reset code'
            );
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top', 'bottom']}>
            <KeyboardAvoidingView
                style={styles.keyboardView}
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            >
                <ScrollView
                    contentContainerStyle={styles.scrollContent}
                    keyboardShouldPersistTaps="handled"
                    showsVerticalScrollIndicator={false}
                >
                    <View style={styles.content}>
                        {/* Logo Section */}
                        <View style={styles.logoSection}>
                            <View style={[styles.logoContainer, { backgroundColor: colors.tint }]}>
                                <Ionicons name="shield-checkmark" size={48} color="#fff" />
                            </View>
                            <Text style={[styles.appName, { color: colors.text }]}>Reset Password</Text>
                            <Text style={[styles.tagline, { color: colors.icon }]}>
                                Enter the code from your email and create a new password
                            </Text>
                        </View>

                        {/* Form Card */}
                        <View style={[styles.formCard, { backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#fff', borderColor: colors.icon + '30' }]}>
                            <View style={styles.inputContainer}>
                                <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                    <Ionicons name="key-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                    <TextInput
                                        style={[styles.input, { color: colors.text }]}
                                        placeholder="Reset code from email"
                                        placeholderTextColor={colors.icon}
                                        value={token}
                                        onChangeText={setToken}
                                        autoCapitalize="none"
                                        autoCorrect={false}
                                        editable={!isLoading}
                                    />
                                </View>
                            </View>

                            <View style={styles.inputContainer}>
                                <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                    <Ionicons name="lock-closed-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                    <TextInput
                                        style={[styles.input, { color: colors.text }]}
                                        placeholder="New password"
                                        placeholderTextColor={colors.icon}
                                        value={password}
                                        onChangeText={setPassword}
                                        secureTextEntry
                                        autoCapitalize="none"
                                        editable={!isLoading}
                                    />
                                </View>
                                <Text style={[styles.hint, { color: colors.icon }]}>
                                    8+ chars with uppercase, lowercase & number
                                </Text>
                            </View>

                            <View style={styles.inputContainer}>
                                <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                    <Ionicons name="shield-checkmark-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                    <TextInput
                                        style={[styles.input, { color: colors.text }]}
                                        placeholder="Confirm new password"
                                        placeholderTextColor={colors.icon}
                                        value={confirmPassword}
                                        onChangeText={setConfirmPassword}
                                        secureTextEntry
                                        autoCapitalize="none"
                                        editable={!isLoading}
                                    />
                                </View>
                            </View>

                            <TouchableOpacity
                                style={[styles.button, isLoading && styles.buttonDisabled]}
                                onPress={handleSubmit}
                                disabled={isLoading}
                            >
                                {isLoading ? (
                                    <ActivityIndicator color="#fff" />
                                ) : (
                                    <>
                                        <Text style={styles.buttonText}>Reset Password</Text>
                                        <Ionicons name="checkmark-circle" size={20} color="#fff" style={styles.buttonIcon} />
                                    </>
                                )}
                            </TouchableOpacity>
                        </View>

                        {/* Footer */}
                        <View style={styles.footer}>
                            <Text style={[styles.footerText, { color: colors.icon }]}>
                                Remember your password?{' '}
                            </Text>
                            <TouchableOpacity
                                onPress={() => router.push('/login')}
                                disabled={isLoading}
                            >
                                <Text style={[styles.link, { color: colors.tint }]}>Sign In</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </ScrollView>
            </KeyboardAvoidingView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    keyboardView: {
        flex: 1,
    },
    scrollContent: {
        flexGrow: 1,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        padding: 24,
    },
    logoSection: {
        alignItems: 'center',
        marginBottom: 24,
    },
    logoContainer: {
        width: 100,
        height: 100,
        borderRadius: 28,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 16,
    },
    appName: {
        fontSize: 28,
        fontWeight: 'bold',
        marginBottom: 8,
        textAlign: 'center',
    },
    tagline: {
        fontSize: 15,
        textAlign: 'center',
        lineHeight: 22,
        paddingHorizontal: 16,
    },
    formCard: {
        borderRadius: 16,
        padding: 24,
        borderWidth: 1,
        marginBottom: 24,
    },
    inputContainer: {
        marginBottom: 16,
    },
    inputWrapper: {
        flexDirection: 'row',
        alignItems: 'center',
        height: 56,
        borderWidth: 1,
        borderRadius: 12,
        paddingHorizontal: 16,
    },
    inputIcon: {
        marginRight: 12,
    },
    input: {
        flex: 1,
        fontSize: 16,
        height: '100%',
    },
    hint: {
        fontSize: 12,
        marginTop: 6,
        marginLeft: 4,
    },
    button: {
        backgroundColor: '#10b981',
        height: 56,
        borderRadius: 12,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 8,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: '600',
    },
    buttonIcon: {
        marginLeft: 8,
    },
    footer: {
        flexDirection: 'row',
        justifyContent: 'center',
    },
    footerText: {
        fontSize: 15,
    },
    link: {
        fontSize: 15,
        fontWeight: '600',
    },
});
